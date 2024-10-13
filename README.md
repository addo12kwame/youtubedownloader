YouTube Downloader
A simple YouTube video downloader built using Django and PyTube.

About

The YouTube Downloader is a web application that allows users to download YouTube videos by providing a video link. It is built with Django on the backend and uses PyTube for handling the YouTube video downloading. This project serves as a simple demonstration of how to integrate video downloading functionality in a web application.
Features


Installation

    Clone the repository:

git clone https://github.com/addo12kwame/youtubedownloader.git
cd youtubedownloader

Create and activate a virtual environment:

python -m venv venv
source venv/bin/activate   # On Windows, use `venv\Scripts\activate`

Install the required dependencies:

  pip install -r requirements.txt

Run the Django development server:

    python manage.py runserver

    Open your browser and go to http://127.0.0.1:8000 to use the application.

Usage

    Paste a YouTube video link into the input field.
    Click the Download button.
    The video will be downloaded and saved to your device.
    View recent downloads or clear the list.


Contributing

Contributions are welcome! If you have suggestions, bug reports, or would like to help out, follow the steps below:

    Fork the project.
    Create your feature branch (git checkout -b feature/YourFeature).
    Commit your changes (git commit -m 'Add Your Feature').
    Push to the branch (git push origin feature/YourFeature).
    Open a pull request.
