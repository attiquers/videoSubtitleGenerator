### 🎬 AI Subtitle Generator

Live Demo: [https://attiquers-ai-subtitles.streamlit.app/](https://attiquers-ai-subtitles.streamlit.app/)

This is a Streamlit application that generates stylized subtitles for a video using the **Faster-Whisper** model. You can customize the appearance of the subtitles and get a live preview before rendering the final video.

#### Features

  * **Transcription:** Uses the `faster-whisper` library to transcribe audio from a video file.
  * **Customizable Styles:** Offers extensive controls to customize subtitle font size, color, position, and background.
  * **Active Word Highlighting:** Highlights the currently spoken word with a different style. This can be disabled if not needed.
  * **Live Preview:** Provides a real-time preview of how the subtitles will look on a blank video canvas.
  * **Model Selection:** Allows you to select and download different **Faster-Whisper** models from Hugging Face.
  * **SRT Editing:** You can edit the transcribed text in SRT format before rendering the final video.

-----

### Setup and Installation

#### 1\. Clone the repository

```bash
git clone <repository-url>
cd subtitleGenerator
```

#### 2\. Install dependencies

```bash
pip install -r requirements.txt
```

-----

### Usage

#### 1\. Model Setup

The **`tiny.en`** model is included by default. For better accuracy, you need to download a larger model.

  * **Using a Hugging Face Token:**
    You can add a Hugging Face token to a secrets file for automatic model downloads.

    1.  Create a folder named **`.streamlit`** in your project's root directory.
    2.  Inside the **`.streamlit`** folder, create a file named **`secrets.toml`**.
    3.  Add your Hugging Face token to the **`secrets.toml`** file in the following format:

    <!-- end list -->

    ```toml
    [huggingface]
    token = "your_huggingface_token_here"
    ```

    The application will now be able to download larger models (e.g., `base.en`, `small.en`, `medium.en`) directly from Hugging Face when you select them.

  * **Manual Download:**
    Alternatively, you can manually download a model from the provided drive link and place its files in the **`models`** folder. For example, to use `small.en`, download the model files and place them in **`models/small.en/`**.

#### 2\. Run the application

To start the subtitle generator, run the following command from the project root:

```bash
streamlit run app.py
```

The application will open in your web browser.

#### 3\. Workflow

1.  **Select a Model:** Choose a model from the options provided. The `tiny.en` model is fast but less accurate. Larger models offer better accuracy but require more time and resources.
2.  **Upload Video:** Upload your video file (`.mp4` format is recommended).
3.  **Transcribe:** Click the **"Transcribe Video"** button. The application will first extract the audio, then transcribe it.
4.  **Edit Subtitles (Optional):** Once the transcription is complete, you can review and edit the text in the provided SRT editor.
5.  **Customize Styles:** Use the sidebar to adjust the subtitle styles, such as font, size, colors, and position. A live preview will update as you make changes.
6.  **Generate Video:** Click the **"Generate Subtitled Video"** button. The application will render a new video with the custom subtitles embedded. You can then download the final video.