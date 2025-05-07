# LMS 2025 NFL Survivor Pool

A web application for managing NFL Survivor Pool contests for the 2025 season.

## Project Overview

LMS 2025 (Last Man Standing) is a platform that allows users to:
- Create and manage survivor pool entries
- Make weekly team picks
- Track standings and results
- Receive email notifications for picks and reminders

## Setup Instructions

### Prerequisites
- Python 3.9+ 
- PostgreSQL
- Git

### Installation

1. Clone the repository:
```
git clone https://github.com/YOUR-USERNAME/lms2025.git
cd lms2025
```

2. Create a virtual environment and activate it:
```
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies:
```
pip install -r requirements.txt
```

4. Create a `.env` file based on `.env.example`

5. Run migrations:
```
python manage.py migrate
```

6. Load initial data:
```
python manage.py loaddata nfl_teams.json
python manage.py loaddata weeks_2025.json
```

7. Create a superuser:
```
python manage.py createsuperuser
```

8. Run the development server:
```
python manage.py runserver
```

## Project Structure

- `lms2025/` - Main Django project settings
- `pool/` - Core app for survivor pool functionality
- `users/` - User authentication and profile management
- `fixtures/` - Initial data (teams, weeks)

## Key Features

- User registration and authentication
- Multiple entries per user
- Weekly team selection with no-repeat rule
- Double-pick weeks (one win to survive)
- Email confirmations and reminders
- Admin override capabilities with audit logging
