# GitHub Quickstart — LALSTUDY

From PowerShell inside the project folder:

```powershell
git init
git add .
git commit -m "LALSTUDY v0.1.0-beta"
git branch -M main
```

Create an empty GitHub repository named:

```text
LALSTUDY
```

Then connect it:

```powershell
git remote add origin https://github.com/YOUR_GITHUB_ID/LALSTUDY.git
git push -u origin main
```

Create the first version tag:

```powershell
git tag -a v0.1.0-beta -m "LALSTUDY v0.1.0-beta"
git push origin v0.1.0-beta
```

After that, create a GitHub Release using the same tag.

For each future update:

```powershell
git add .
git commit -m "Describe the update"
git push
```

For milestone versions:

```powershell
git tag -a v0.2.0-beta -m "LALSTUDY v0.2.0-beta"
git push origin v0.2.0-beta
```


## Publish v0.2.0-beta

After copying the v0.2 files into your existing local repository:

```powershell
git add .
git commit -m "Release LALSTUDY v0.2.0-beta AI Deep Study"
git push
git tag -a v0.2.0-beta -m "LALSTUDY v0.2.0-beta"
git push origin v0.2.0-beta
```

For Streamlit Community Cloud, add `OPENAI_API_KEY` under the app's Secrets settings. Add `OPENAI_ADMIN_KEY` as well if you want official organization usage/cost sync.
