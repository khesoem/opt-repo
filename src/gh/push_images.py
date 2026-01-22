#!/usr/bin/env python3
"""
Script to push all Docker images containing 'optds' in their name to GitHub Container Registry (ghcr.io)
and make them public.
"""

import subprocess
import sys
import json
from typing import List, Tuple
from src.utils import run_cmd


def get_github_username() -> str:
    """Get the GitHub username using gh CLI."""
    try:
        result = run_cmd(['gh', 'api', 'user'], '.', capture_output=True)
        user_data = json.loads(result)
        return user_data['login']
    except Exception as e:
        print(f"Error getting GitHub username: {e}", file=sys.stderr)
        sys.exit(1)


def get_docker_images_with_optds() -> List[Tuple[str, str]]:
    """
    Get all Docker images that contain 'optds' in their name.
    Returns a list of tuples (repository, tag).
    """
    try:
        result = run_cmd(['docker', 'images', '--format', '{{.Repository}}:{{.Tag}}'], '.', capture_output=True)
        images = []
        for line in result.strip().split('\n'):
            if line and 'optds' in line.lower():
                # Split repository and tag
                if ':' in line:
                    repo, tag = line.rsplit(':', 1)
                else:
                    repo = line
                    tag = 'latest'
                images.append((repo, tag))
        return images
    except Exception as e:
        print(f"Error listing Docker images: {e}", file=sys.stderr)
        sys.exit(1)


def tag_image_for_ghcr(repo: str, tag: str, username: str) -> str:
    """Tag an image for ghcr.io. Returns the new image name."""
    # Create a clean image name for ghcr (lowercase, no special chars except - and /)
    # Replace any existing registry prefix and normalize
    image_name = repo.split('/')[-1].lower()  # Get last part of repo name
    ghcr_image = f"ghcr.io/{username}/{image_name}:{tag}"
    
    # Tag the image
    try:
        run_cmd(['docker', 'tag', f"{repo}:{tag}", ghcr_image], '.', capture_output=False)
        print(f"Tagged {repo}:{tag} -> {ghcr_image}")
        return ghcr_image
    except Exception as e:
        print(f"Error tagging image {repo}:{tag}: {e}", file=sys.stderr)
        raise


def push_image_to_ghcr(ghcr_image: str):
    """Push an image to ghcr.io."""
    try:
        run_cmd(['docker', 'push', ghcr_image], '.', capture_output=False)
        print(f"Pushed {ghcr_image}")
    except Exception as e:
        print(f"Error pushing image {ghcr_image}: {e}", file=sys.stderr)
        raise


def main():

    print("Getting GitHub username...")
    username = get_github_username()
    print(f"GitHub username: {username}\n")
    
    print("Finding Docker images with 'optds' in their name...")
    images = get_docker_images_with_optds()
    
    if not images:
        print("No images found with 'optds' in their name.")
        return
    
    print(f"Found {len(images)} image(s):")
    for repo, tag in images:
        print(f"  - {repo}:{tag}")
    print()
    
    # Process each image
    for repo, tag in images:
        try:
            print(f"Processing {repo}:{tag}...")
            
            # Tag for ghcr
            ghcr_image = tag_image_for_ghcr(repo, tag, username)
            
            # Push to ghcr
            push_image_to_ghcr(ghcr_image)
            
            print(f"✓ Successfully processed {repo}:{tag}\n")
        except Exception as e:
            print(f"✗ Failed to process {repo}:{tag}: {e}\n", file=sys.stderr)
            continue
    
    print("Done!")


if __name__ == '__main__':
    main()
