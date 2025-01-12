# YouTube Downloader Web App

A Flask-based web application for downloading YouTube videos with user authentication and download progress tracking.

## Features

- User registration and authentication
- Secure password storage with hashing
- Download history tracking
- Real-time download progress with speed and ETA
- Multiple format selection
- Responsive UI with Bootstrap 5

## Prerequisites

Before installing, make sure you have Python 3.8+ installed on your system.

### Windows
1. Download Python from [python.org](https://www.python.org/downloads/)
2. During installation, make sure to check "Add Python to PATH"
3. Install Git from [git-scm.com](https://git-scm.com/download/win)

### macOS
Using Homebrew:
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python and Git
brew install python git
```

### Linux

#### Debian/Ubuntu
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git
```

#### Arch Linux
```bash
sudo pacman -Syu
sudo pacman -S python python-pip git
```

#### Fedora
```bash
sudo dnf update
sudo dnf install python3 python3-pip git
```

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/youtubedownloaderweb.git
cd youtubedownloaderweb
```

2. Create and activate virtual environment:

Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
# Windows
pip install -r requirements.txt

# macOS/Linux
pip3 install -r requirements.txt
```

4. Set up environment variables:
```bash
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env
```

Edit the `.env` file and add your own values for:
- SECRET_KEY: A random string for Flask session security
- ENCRYPTION_KEY: Generate using:
  ```bash
  # Windows
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  
  # macOS/Linux
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

5. Initialize the database:

Windows:
```bash
python
>>> from app import db, app
>>> with app.app_context():
...     db.create_all()
>>> exit()
```

macOS/Linux:
```bash
python3
>>> from app import db, app
>>> with app.app_context():
...     db.create_all()
>>> exit()
```

6. Run the application:

Windows:
```bash
python app.py
```

macOS/Linux:
```bash
python3 app.py
```

7. Open your browser and navigate to `http://localhost:5000`

## Troubleshooting

### Windows
- If `python` command is not found, try using `py` instead
- Make sure Python is added to PATH during installation
- If you get SSL errors, download and install [Windows Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)

### macOS
- If you get permission errors, use `sudo` with pip commands
- If Homebrew is not found, add it to PATH:
  ```bash
  echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
  eval "$(/opt/homebrew/bin/brew shellenv)"
  ```

### Linux
- If you get permission errors with pip, use:
  ```bash
  pip3 install --user -r requirements.txt
  ```
- If you get build errors, install build dependencies:
  
  Debian/Ubuntu:
  ```bash
  sudo apt install python3-dev build-essential
  ```
  
  Arch Linux:
  ```bash
  sudo pacman -S base-devel
  ```
  
  Fedora:
  ```bash
  sudo dnf groupinstall "Development Tools"
  ```

## Usage

1. Register a new account or login with existing credentials
2. On the dashboard, enter a YouTube video URL
3. Select your preferred video format from the available options
4. Start the download and monitor progress in real-time
5. View your download history in the dashboard

## Security Features

- Password hashing using Werkzeug's security functions
- Flask-Login for session management
- Local storage of all user data
- Encrypted sensitive information
- CSRF protection with Flask-WTF

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details
