import re
import os

def fix_views_file():
    """
    Update all timezone.now().date() calls to timezone.now() in views.py file
    to properly handle datetime fields.
    """
    views_file = os.path.join('pool', 'views.py')
    
    # Read the file content
    with open(views_file, 'r') as f:
        content = f.read()
    
    # Replace timezone.now().date() with timezone.now() in all queries
    new_content = re.sub(r'timezone\.now\(\)\.date\(\)', 'timezone.now()', content)
    
    # Write the updated content back to the file
    with open(views_file, 'w') as f:
        f.write(new_content)
    
    print(f"Updated datetime queries in {views_file}")

if __name__ == "__main__":
    fix_views_file()
