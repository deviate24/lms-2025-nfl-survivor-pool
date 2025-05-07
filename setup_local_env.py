"""
Setup script for local development environment.
This script creates a .env file with development settings.
"""
import os
import secrets
import shutil

def main():
    """Create a .env file for local development."""
    # Check if .env file already exists
    if os.path.exists('.env'):
        overwrite = input('.env file already exists. Overwrite? (y/n): ')
        if overwrite.lower() != 'y':
            print('Setup cancelled.')
            return
    
    # Generate a random secret key
    secret_key = secrets.token_urlsafe(50)
    
    # Create .env file content
    env_content = f"""# Django settings
SECRET_KEY={secret_key}
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database settings - SQLite for development
# For PostgreSQL, uncomment and update the following line:
# DATABASE_URL=postgres://user:password@localhost:5432/lms2025

# Email settings - Console backend for development
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
# For SMTP, uncomment and update the following lines:
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# EMAIL_HOST=smtp.example.com
# EMAIL_PORT=587
# EMAIL_HOST_USER=your-email@example.com
# EMAIL_HOST_PASSWORD=your-email-password
# EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=LMS 2025 <noreply@example.com>

# Time zone
TIME_ZONE=America/Los_Angeles
"""
    
    # Write to .env file
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print('.env file created successfully with development settings.')
    print('To run the project:')
    print('1. Create a virtual environment: python -m venv venv')
    print('2. Activate the virtual environment:')
    print('   - Windows: venv\\Scripts\\activate')
    print('   - Unix/MacOS: source venv/bin/activate')
    print('3. Install dependencies: pip install -r requirements.txt')
    print('4. Run migrations: python manage.py migrate')
    print('5. Load initial data:')
    print('   - python manage.py loaddata fixtures/nfl_teams.json')
    print('   - python manage.py loaddata fixtures/weeks_2025.json')
    print('6. Create a superuser: python manage.py createsuperuser')
    print('7. Run the development server: python manage.py runserver')

if __name__ == '__main__':
    main()
