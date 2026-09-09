# LALSTUDY translation hotfix

Replace your existing `translator.py` with the file in this folder.

This hotfix:
- rejects Google `Error 500 / Server Error` HTML responses
- retries transient Google failures
- uses larger chunks to reduce request count
- caches translations for 30 days
- attempts MyMemory as a fallback
- falls back to the original English source instead of displaying an error page
- preserves scientific terms where possible

No change to `Learn a Paper` is required if your current v0.1.1 beta already imports `translator.py`.

After replacing:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address=127.0.0.1
```

Then commit:

```powershell
git add translator.py
git commit -m "Fix translation 500 errors"
git push
```
