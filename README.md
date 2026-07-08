# morrison.im

Personal site for Chris Morrison. The site is intentionally simple: a landing page, an archive, a projects page, and a handful of static post pages.

## Structure

- `index.html` - landing page with bio, featured posts, projects, and links
- `archive.html` - chronological list of posts
- `projects.html` - project notes and public links
- `posts/` - individual static post pages
- `style.css` - shared typography and layout
- `404.html` - GitHub Pages-friendly not found page

## Local preview

Run a simple static server from the repo root:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

## GitHub Pages

This site has no build step. Configure GitHub Pages to publish from the repository root on the main branch, or from the branch you use for deployment.

If using a custom domain, configure it in the GitHub Pages settings for the repository.
