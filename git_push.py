import os
from git import Repo
import sys

def push_to_github():
    try:
        # Configure git with token
        repo = Repo('.')
        
        # Set up the remote URL with token
        github_token = os.environ.get('GITHUB_TOKEN')
        if not github_token:
            print("Error: GitHub token not found in environment variables")
            return False
            
        remote_url = f"https://x-access-token:{github_token}@github.com/Alujan18/flask-auth-system.git"
        
        # Check if 'origin' remote exists
        try:
            origin = repo.remote('origin')
            # Update origin URL with token
            origin.set_url(remote_url)
        except ValueError:
            # Add origin if it doesn't exist
            origin = repo.create_remote('origin', remote_url)
            
        # Push to GitHub
        origin.push()
        print("Successfully pushed changes to GitHub")
        return True
        
    except Exception as e:
        print(f"Error pushing to GitHub: {str(e)}")
        return False

if __name__ == "__main__":
    success = push_to_github()
    sys.exit(0 if success else 1)
