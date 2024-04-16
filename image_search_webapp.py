import os
import numpy as np
from PIL import Image
import streamlit as st
import uform
from simsimd import cosine
import pickle
import pandas as pd
import requests
import streamlit.components.v1 as components


# Backend
def load_embeddings(folder_path):
    embedding_path = os.path.join(folder_path, "embeddings.pkl")
    file_paths_path = os.path.join(folder_path, "file_paths.pkl")
    if os.path.exists(embedding_path) and os.path.exists(file_paths_path):
        with open(embedding_path, "rb") as f:
            embeddings = pickle.load(f)
        with open(file_paths_path, "rb") as f:
            file_paths = pickle.load(f)
        return embeddings, file_paths
    return None, None

def save_embeddings(folder_path, embeddings, file_paths):
    embedding_path = os.path.join(folder_path, "embeddings.pkl")
    file_paths_path = os.path.join(folder_path, "file_paths.pkl")
    with open(embedding_path, "wb") as f:
        pickle.dump(embeddings, f)
    with open(file_paths_path, "wb") as f:
        pickle.dump(file_paths, f)

def embed_images(folder_path, model, processor, max_size=(224, 224)):
    embeddings = []
    file_paths = []
    folder_path = os.path.abspath(folder_path)
   
    image_files = [file for file in os.listdir(folder_path) if file.endswith((".jpg", ".jpeg", ".png"))]
    total_files = len(image_files)
    progress_bar = st.progress(0, text=f"Embedding images... (0/{total_files})")
   
    for index, file in enumerate(image_files, start=1):
        file_path = os.path.join(folder_path, file)
        image = Image.open(file_path).resize(max_size)
        image_data = processor.preprocess_image(image)
        image_embedding = model.encode_image(image_data, return_features=False).detach().numpy()
        image_embedding = np.squeeze(image_embedding)  # Remove extra dimensions
        embeddings.append(image_embedding)
        file_paths.append(file_path)
        progress_bar.progress(index / total_files, text=f"Embedding images... ({index}/{total_files})")
   
    return np.array(embeddings), file_paths

def search_images(query, embeddings, file_paths, model, processor, top_k=7):
    text_data = processor.preprocess_text(query)
    text_embedding = model.encode_text(text_data, return_features=False).detach().numpy()
   
    if embeddings.ndim > 2:
        embeddings = embeddings.reshape(embeddings.shape[0], -1)
   
    if text_embedding.ndim == 1:
        text_embedding = text_embedding.reshape(1, -1)
    elif text_embedding.ndim != 2:
        raise ValueError("Text embedding must be a 1D or 2D numpy array.")
   
    # Normalize the embeddings
    embeddings_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    text_embedding_norm = text_embedding / np.linalg.norm(text_embedding, axis=1, keepdims=True)
   
    # Calculate the cosine similarity
    similarities = np.dot(embeddings_norm, text_embedding_norm.T).flatten()
   
    top_indices = similarities.argsort()[-top_k:][::-1]
    return [file_paths[i] for i in top_indices], similarities[top_indices]


def display_slideshow(images_urls):
    if len(images_urls) > 1:        # Display slideshow for multiple images
        components.html(
            f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    /* CSS styles for the slideshow */
                    .mySlides {{display: none;}}
                    img {{vertical-align: middle;}}
                    .slideshow-container {{
                        max-width: 800px;
                        position: relative;
                        margin: auto;
                    }}                    .prev, .next {{
                        cursor: pointer;
                        position: absolute;
                        top: 50%;
                        width: auto;
                        padding: 16px;
                        margin-top: -22px;
                        color: white;
                        font-weight: bold;
                        font-size: 18px;
                        transition: 0.6s ease;
                        border-radius: 0 3px 3px 0;
                        user-select: none;
                    }}
                    .next {{
                        right: 0;
                        border-radius: 3px 0 0 3px;
                    }}
                    .prev:hover, .next:hover {{
                        background-color: rgba(0,0,0,0.8);
                    }}
                    .numbertext {{
                        color: #f2f2f2;
                        font-size: 12px;
                        padding: 8px 12px;
                        position: absolute;
                        top: 0;
                    }}
                    .dot {{
                        cursor: pointer;
                        height: 15px;
                        width: 15px;
                        margin: 0 2px;
                        background-color: #bbb;
                        border-radius: 50%;                        display: inline-block;
                        transition: background-color 0.6s ease;
                    }}
                    .active, .dot:hover {{
                        background-color: #717171;                    }}
                </style>
            </head>
            <body>
                <div class="slideshow-container">
                    {''.join([f'<div class="mySlides"><div class="numbertext">{i+1} / {len(images_urls)}</div><img src="{url}" style="width:100%"></div>' for i, url in enumerate(images_urls)])}
                    <a class="prev" onclick="plusSlides(-1)">&#10094;</a>
                    <a class="next" onclick="plusSlides(1)">&#10095;</a>
                </div>
                <br>
                <div style="text-align:center">
                    {''.join([f'<span class="dot" onclick="currentSlide({i+1})"></span>' for i in range(len(images_urls))])}
                </div>
                <script>
                    let slideIndex = 1;
                    showSlides(slideIndex);
                    function plusSlides(n) {{
                        showSlides(slideIndex += n);
                    }}
                    function currentSlide(n) {{
                        showSlides(slideIndex = n);
                    }}
                    function showSlides(n) {{
                        let i;
                        let slides = document.getElementsByClassName("mySlides");
                        let dots = document.getElementsByClassName("dot");
                        if (n > slides.length) {{slideIndex = 1}}
                        if (n < 1) {{slideIndex = slides.length}}
                        for (i = 0; i < slides.length; i++) {{
                            slides[i].style.display = "none";
                        }}
                        for (i = 0; i < dots.length; i++) {{
                            dots[i].className = dots[i].className.replace(" active", "");
                        }}
                        slides[slideIndex-1].style.display = "block";
                        dots[slideIndex-1].className += " active";
                    }}                </script>
            </body>
            </html>
            """,
            height=400,
        )
    elif len(images_urls) == 1:
        # Display single image
        try:
            image = Image.open(requests.get(images_urls[0], stream=True).raw)
            image.thumbnail((800, 800))            
            st.image(image)
        except Exception as e:
            st.warning(f"Error loading image: {str(e)}")


def display_tweet(tweet_data):
    with st.expander(f"Tweet by {tweet_data['author_name']}", expanded=True):
        col1, col2 = st.columns([4, 2])
        with col1:
            if tweet_data['images_urls'] is not None and len(tweet_data['images_urls']) > 0:
                display_slideshow(tweet_data['images_urls'])
        with col2:
            st.write(f"**Author:** [{tweet_data['author_name']}]({tweet_data['url']})")
            st.write(f"**Date:** {tweet_data['date'].strftime('%Y-%m-%d')}")
            st.write(tweet_data['text'])
            st.write(f"**Likes:** {tweet_data['num_like']} | **Retweets:** {tweet_data['num_retweet']} | **Replies:** {tweet_data['num_reply']}")


def load_data_df(file_path):
    df = pd.read_json(file_path, lines=True)
    df['date'] = pd.to_datetime(df['date'], format='%d/%m/%Y')
    return df


def display_slideshow(images_urls):
    if len(images_urls) > 1:
        # Display slideshow for multiple images
        components.html(
            f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    /* CSS styles for the slideshow */
                    .mySlides {{display: none;}}
                    img {{vertical-align: middle;}}
                    .slideshow-container {{
                        max-width: 800px;
                        position: relative;
                        margin: auto;
                    }}
                    .prev, .next {{
                        cursor: pointer;
                        position: absolute;
                        top: 50%;
                        width: auto;
                        padding: 16px;
                        margin-top: -22px;
                        color: white;
                        font-weight: bold;
                        font-size: 24px;
                        transition: 0.6s ease;
                        border-radius: 0 3px 3px 0;
                        user-select: none;
                        background-color: rgba(0,0,0,0.5);
                    }}
                    .next {{
                        right: 0;
                        border-radius: 3px 0 0 3px;
                    }}
                    .prev:hover, .next:hover {{
                        background-color: rgba(0,0,0,0.8);
                    }}
                    .numbertext {{
                        color: #f2f2f2;
                        font-size: 12px;
                        padding: 8px 12px;
                        position: absolute;
                        top: 0;
                    }}
                    .dot {{
                        cursor: pointer;
                        height: 15px;
                        width: 15px;
                        margin: 0 2px;
                        background-color: #bbb;
                        border-radius: 50%;
                        display: inline-block;
                        transition: background-color 0.6s ease;
                    }}
                    .active, .dot:hover {{
                        background-color: #717171;
                    }}
                </style>
            </head>
            <body>
                <div class="slideshow-container">
                    {''.join([f'<div class="mySlides"><div class="numbertext">{i+1} / {len(images_urls)}</div><img src="{url}" style="width:100%"></div>' for i, url in enumerate(images_urls)])}
                    <a class="prev" onclick="plusSlides(-1)">&#10094;</a>
                    <a class="next" onclick="plusSlides(1)">&#10095;</a>
                </div>
                <br>
                <div style="text-align:center">
                    {''.join([f'<span class="dot" onclick="currentSlide({i+1})"></span>' for i in range(len(images_urls))])}
                </div>
                <script>
                    let slideIndex = 1;
                    showSlides(slideIndex);
                    function plusSlides(n) {{
                        showSlides(slideIndex += n);
                    }}
                    function currentSlide(n) {{
                        showSlides(slideIndex = n);
                    }}
                    function showSlides(n) {{
                        let i;
                        let slides = document.getElementsByClassName("mySlides");
                        let dots = document.getElementsByClassName("dot");
                        if (n > slides.length) {{slideIndex = 1}}
                        if (n < 1) {{slideIndex = slides.length}}
                        for (i = 0; i < slides.length; i++) {{
                            slides[i].style.display = "none";
                        }}
                        for (i = 0; i < dots.length; i++) {{
                            dots[i].className = dots[i].className.replace(" active", "");
                        }}
                        slides[slideIndex-1].style.display = "block";
                        dots[slideIndex-1].className += " active";
                    }}
                </script>
            </body>
            </html>
            """,
            height=400,
        )
    elif len(images_urls) == 1:
        # Display single image
        try:
            image = Image.open(requests.get(images_urls[0], stream=True).raw)
            image.thumbnail((800, 800))
            st.image(image)
        except Exception as e:
            st.warning(f"Error loading image: {str(e)}")

def display_tweet(tweet_data):
    with st.expander(f"Tweet by {tweet_data['author_name']}", expanded=True):
        col1, col2 = st.columns([4, 2])
        with col1:
            if tweet_data['images_urls'] is not None and len(tweet_data['images_urls']) > 0:
                display_slideshow(tweet_data['images_urls'])
        with col2:
            st.write(f"**Author:** [{tweet_data['author_name']}]({tweet_data['url']})")
            st.write(f"**Date:** {tweet_data['date'].strftime('%Y-%m-%d')}")
            st.write(tweet_data['text'])
            st.write(f"**Likes:** {tweet_data['num_like']} | **Retweets:** {tweet_data['num_retweet']} | **Replies:** {tweet_data['num_reply']}")


def main():
    st.set_page_config(page_title="Image Search App", layout="wide")
   


    main_container = st.container()
    with main_container:
        logo_col, title_col = st.columns([1.2, 8.5])
        with logo_col:
            st.image("images/twitter_Suprematism2.png", width=200)
        with title_col:
            st.markdown(
                """
                <style>
                @import url('https://fonts.googleapis.com/css2?family=Josefin+Slab&display=swap');
                .title {
                    font-family: 'Josefin Slab', serif;
                    font-size: 48px;
                    font-weight: bold;
                    margin-top: 120px;
                }
                </style>
                <div class="title">Twitter Insight with Image Search</div>
                """,
                unsafe_allow_html=True,
            )        
        st.markdown("Quick PoC to search images based on text query using tiny multi-language image embedding model. \n\nMake sure download images and tweet data before searching.")

        if 'embeddings' not in st.session_state:
            st.session_state.embeddings = None
        if 'file_paths' not in st.session_state:
            st.session_state.file_paths = None
        if 'model' not in st.session_state:
            st.session_state.model = None
        if 'processor' not in st.session_state:
            st.session_state.processor = None
        if 'data_df' not in st.session_state:
            st.session_state.data_df = None

        with st.expander("Instructions", expanded=True):
            folder_path = st.text_input("Enter the folder path containing images:", value="downloaded_images")
            data_file_path = st.text_input("Enter the path to the tweet data file:", value="data/sample_output_json.json")
            model_name = st.selectbox("Select the UForm model:", ["unum-cloud/uform-vl-multilingual-v2", "unum-cloud/uform-vl-english-large"])
            top_k = st.number_input("Enter the number of top results to display:", min_value=1, value=6)

            if st.button("Load Tweet Data"):
                if not data_file_path:
                    st.warning("Please enter the path to the tweet data file.")
                else:
                    st.session_state.data_df = load_data_df(data_file_path)
                    st.success(f"Loaded {len(st.session_state.data_df)} tweets.")
        
            if st.button("Embed Images"):
                if not folder_path:
                    st.warning("Please enter a folder path.")
                else:
                    st.session_state.model, st.session_state.processor = uform.get_model(model_name)
                    st.session_state.embeddings, st.session_state.file_paths = load_embeddings(folder_path)
                    if st.session_state.embeddings is None or st.session_state.file_paths is None:
                        st.session_state.embeddings, st.session_state.file_paths = embed_images(folder_path, st.session_state.model, st.session_state.processor)
                        save_embeddings(folder_path, st.session_state.embeddings, st.session_state.file_paths)
                        st.success(f"Embedded {len(st.session_state.file_paths)} images.")
                    else:
                        st.info("Using previously embedded images.")
        
        query = st.text_input("Enter a search query:", key="query_input", on_change=lambda: st.session_state.update(search_button=True))
        st.session_state.search_button = False
    
        if st.button("Search") or st.session_state.search_button:
            if query is None or query.strip() == "":
                st.warning("Please enter a search query.")
            elif st.session_state.file_paths is None:
                st.warning("Please provide file_paths first.")
            elif st.session_state.embeddings is None:
                st.warning("Please embed the images first.")
            elif st.session_state.data_df is None:
                st.warning("Please load the tweet data first.")
            else:
                top_files, similarities = search_images(query, st.session_state.embeddings, st.session_state.file_paths, st.session_state.model, st.session_state.processor, top_k)
            
                st.subheader(f"Top {top_k} Results:")
                st.write("Sometimes one tweet conatins more than one images, click on the images to view more.")
                unique_tweet_urls = set()
                cols = st.columns(3)
                for i, (file, similarity) in enumerate(zip(top_files, similarities)):
                    image_id = os.path.splitext(os.path.basename(file))[0]
                    twitter_name = image_id.split("__")[0]
                    tweet_id = image_id.split("__")[1].split("_")[0]
                    tweet_url = f"https://twitter.com/{twitter_name}/status/{tweet_id}"
                
                    # Check if the tweet URL exists in the data_df and has not been displayed yet
                    if st.session_state.data_df['url'].isin([tweet_url]).any() and tweet_url not in unique_tweet_urls:
                        tweet_data = st.session_state.data_df[st.session_state.data_df['url'] == tweet_url].iloc[0]
                    
                        with cols[i % 3]:
                            try:
                                display_tweet(tweet_data)
                                st.write(f"**Similarity:** {similarity:.3f}")
                            except Exception as e:
                                st.warning(f"Error displaying tweet: {str(e)}")

                        unique_tweet_urls.add(tweet_url)

    # Add footer
    footer="""
    <style>
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: white;
        color: black;
        text-align: center;
        padding: 10px;
    }
    .footer-icon {
        display: inline-flex;
        align-items: center;
        margin: 0 10px;
    }
    .footer-icon img {
        width: 24px;
        height: 24px;
        margin-right: 5px;
    }
    </style>
    <div class="footer">
        <div class="footer-icon">
            <a href="https://github.com/AlexZhangji/Twitter-Insight-LLM" target="_blank">
            Github
                <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/github/github-original.svg" alt="GitHub" />
            </a>
        </div>
        <div class="footer-icon">
            <a href="https://twitter.com/GZhan57" target="_blank">
                Twitter
                <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/twitter/twitter-original.svg" alt="Twitter" />
            </a>
        </div>
    </div>
    """
    st.markdown(footer, unsafe_allow_html=True)

if __name__ == "__main__":
    main()