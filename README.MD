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

This application is designed to be run using Docker, which simplifies the setup process and ensures all dependencies are correctly handled. You will need to have **Docker** and **Docker Compose** installed on your system.

#### 1\. Clone the repository

```bash
git clone <repository-url>
cd subtitleGenerator
```

-----

### Usage

#### 1\. Running with CPU (Recommended for most users) 🐢

To build and run the application using your computer's CPU, use the following command. This is the simplest way to get started. The `--build` flag will create the Docker image if it doesn't already exist.

```bash
docker compose up --build --build-arg USE_GPU=false
```

Once the application is running, open your web browser and navigate to `http://localhost:8502`.

#### 2\. Running with GPU (For faster performance) 🚀

If you have a compatible NVIDIA GPU, you can build and run the application with GPU support for significantly faster transcription. This requires an extra step.

1.  **Enable GPU in `docker-compose.yml`**: Open the `docker-compose.yml` file and uncomment the `deploy` section to allow the container to access your GPU.

    ```yaml
    # services:
    #   subtitle-generator:
    #     ...
    #     deploy:
    #       resources:
    #         reservations:
    #           devices:
    #             - driver: nvidia
    #               count: all
    #               capabilities: [gpu]
    ```

2.  **Run the command**: With the `deploy` section uncommented, run the following command. The `USE_GPU=true` argument tells Docker to install the necessary GPU-compatible libraries.

    ```bash
    docker compose up --build --build-arg USE_GPU=true
    ```

Once the application is running, open your web browser and navigate to `http://localhost:8502`.

#### 3\. Workflow

1.  **Select a Model:** Choose a model from the options provided. The `tiny.en` model is fast but less accurate. Larger models offer better accuracy but require more time and resources.
2.  **Upload Video:** Upload your video file (`.mp4` format is recommended).
3.  **Transcribe:** Click the **"Transcribe Video"** button. The application will first extract the audio, then transcribe it.
4.  **Edit Subtitles (Optional):** Once the transcription is complete, you can review and edit the text in the provided SRT editor.
5.  **Customize Styles:** Use the sidebar to adjust the subtitle styles, such as font, size, colors, and position. A live preview will update as you make changes.
6.  **Generate Video:** Click the **"Generate Subtitled Video"** button. The application will render a new video with the custom subtitles embedded. You can then download the final video.