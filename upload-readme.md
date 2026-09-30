# Repository Upload Guide for Agent

This file contains instructions for the AI assistant on how to successfully push other folders (like `frontend`, `docs`, etc.) to the `Bhu-Darpan` remote repository without encountering timeout errors or size limits.

## Past Issues and Solutions
1. **Massive Git History:** The local `e:\Bhu-Darpan` repository has a massive Git history (from `miniProject`). Trying to push a regular branch to the `Bhu-Darpan` remote causes Git to attempt to upload the entire history, resulting in a timeout. 
   - *Solution:* Always use an **orphan branch** (`git checkout --orphan <branch-name>`) when pushing to `Bhu-Darpan` to ensure only the necessary files are pushed without historical baggage.
2. **Connection Resets (curl 55 / HTTP 408):** Pushing large files (even if under the 100MB limit) or thousands of tiny files all at once (like the 27,000 EuroSAT images) causes the network connection to drop and reset.
   - *Solution:* Push the repository in **smaller, bite-sized chunks**. Commit the source code and smaller files first, push them, and then commit and push larger files/models one by one.
3. **GitHub File Size Limits:** GitHub hard-blocks files over 100MB (like `model_inflow.pkl` which was 124MB).
   - *Solution:* Exclude any file over 50MB using `.gitignore` or `git rm --cached`, unless specifically chunked/zipped.

## Instructions for Uploading Other Folders (e.g., `frontend`, `docs`)

When the user requests to upload the `frontend` or any other folder to the `Bhu-Darpan` repository, execute the following steps precisely:

1. **Create an Orphan Branch:**
   ```bash
   git checkout --orphan <new-branch-name>
   git rm -rf --cached .
   ```

2. **Add the Required Folders/Files:**
   Only stage the specific folders the user requested (e.g., `frontend`), along with any root files they want (`README.md`, `LICENSE`, etc.).
   ```bash
   git add frontend/ README.md LICENSE .gitignore
   ```

3. **Exclude Problematic Files:**
   Ensure no massive files (like `node_modules`, large datasets, `.venv`, or `.git.bak`) are tracked. If they are, remove them from the cache:
   ```bash
   git rm -rf --cached frontend/node_modules
   ```

4. **Commit and Push in Chunks (If necessary):**
   If the folder is large, commit the base files first, push, and then incrementally commit and push the rest:
   ```bash
   git commit -m "Upload frontend base files"
   git push -f Saksham-Singh <new-branch-name>:main
   ```

By following these instructions, you will avoid the `HTTP 408` and `curl 55` timeout errors previously encountered.
