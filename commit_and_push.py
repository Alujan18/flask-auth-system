import os
from git import Repo
import sys

def commit_and_push():
    try:
        # Initialize repo
        repo = Repo('.')
        
        # Add all modified and untracked files
        repo.git.add('.')
        
        # Commit changes
        repo.index.commit("Update dependencies and configuration files")
        
        # Configure remote with token
        github_token = os.environ.get('GITHUB_TOKEN')
        if not github_token:
            print("Error: GitHub token not found in environment variables")
            return False
            
        remote_url = f"https://x-access-token:{github_token}@github.com/Alujan18/flask-auth-system.git"
        
        # Update origin URL
        try:
            origin = repo.remote('origin')
            origin.set_url(remote_url)
        except ValueError:
            origin = repo.create_remote('origin', remote_url)
            
        # Push to GitHub
        origin.push()
        print("Successfully pushed changes to GitHub")
        return True
        
    except Exception as e:
        print(f"Error in commit_and_push: {str(e)}")
        return False

if __name__ == "__main__":
    success = commit_and_push()
    sys.exit(0 if success else 1)
