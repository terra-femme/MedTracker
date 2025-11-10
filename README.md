Note: This is a foundational scaffold for a medication reminder app. Core architecture is in place; features are being developed iteratively to reflect real-world healthcare IT workflows.
# Medication Reminder App

A healthcare application designed to help users manage their medication schedules with timely reminders and tracking.

## Features

- **Medication Tracking**: Add, edit, and organize medications with dosage and frequency information
- **Smart Reminders**: Receive notifications at scheduled times for medication intake
- **Adherence Tracking**: Track whether medications were taken on time
- **Medical History**: View medication history and adherence reports

## Installation

### Requirements
- Python 3.9+
- [Any other dependencies]

### Setup
```bash
# Clone the repository
git clone git@github.com:terra-femme/MedTracker.git
cd medication-reminder-app

# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

## Usage

[Coming Soon: instructions here for how to use app]

### Example
```bash
# Start the app
python main.py

# Add a new medication
# Set reminder time
# Receive notifications
```


## Architecture
MedTracker/
├── backend/               # Flask backend logic
├── frontend/              # HTML/CSS/JS frontend
├── main.py                # Entry point
├── medtracker.db          # SQLite database
├── requirements.txt
├── setup_database.py
├── .gitignore
└── README.md


## Development

### Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes and commit: `git commit -m "Add your feature"`
3. Push: `git push origin feature/your-feature`
4. Create a Pull Request on GitHub

### Running Tests
```bash
pytest tests/
```

## Current Status & Roadmap

- [x] Basic project structure
- [ ] User authentication
- [ ] Medication database
- [ ] Reminder system
- [ ] Notification system
- [ ] Adherence tracking dashboard

## Technologies Used

- Python 3.9+
- Flask
- SQLite
- HTML/CSS/JavaScript


## License

MIT License - Feel free to use this project as reference or foundation

## Author

Kristy aka Terra Femme — Aspiring Healthcare IT Engineer | Focused on modular workflows, Git hygiene, and FHIR-aligned development

---

**Note**: This project is part of my portfolio demonstrating healthcare IT skills and FHIR integration knowledge.
EOF

git add README.md
git commit -m "Add comprehensive README with installation and usage instructions"
git push
