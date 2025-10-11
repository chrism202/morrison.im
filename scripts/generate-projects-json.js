#!/usr/bin/env node

import { readFile, writeFile } from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');
const CONFIG_PATH = path.join(ROOT_DIR, 'projects-config.json');
const OUTPUT_PATH = path.join(ROOT_DIR, 'projects.json');

const GITHUB_TOKEN = process.env.GITHUB_TOKEN || process.env.GH_TOKEN || process.env.TOKEN;

async function readConfig() {
  const raw = await readFile(CONFIG_PATH, 'utf8');
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed.projects)) {
    throw new Error('projects-config.json must include a "projects" array.');
  }
  return parsed.projects;
}

async function fetchRepo(fullName) {
  const url = new URL(`https://api.github.com/repos/${fullName}`);
  const headers = {
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'morrison-im-project-fetcher'
  };

  if (GITHUB_TOKEN) {
    headers.Authorization = `Bearer ${GITHUB_TOKEN}`;
  }

  const response = await fetch(url, { headers });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to fetch ${fullName}: ${response.status} ${response.statusText} - ${text}`);
  }

  return response.json();
}

function buildProject(entry, repoData, error) {
  const now = new Date().toISOString();

  const baseName = entry.repo.includes('/')
    ? entry.repo.split('/')[1]
    : entry.repo;

  const displayName = entry.displayName || repoData?.name || baseName;
  const summary = entry.summary || repoData?.description || '';

  return {
    repo: entry.repo,
    displayName,
    summary,
    description: repoData?.description ?? null,
    htmlUrl: repoData?.html_url ?? null,
    homepage: entry.homepage || repoData?.homepage || null,
    stars: repoData?.stargazers_count ?? null,
    language: repoData?.language ?? null,
    topics: Array.isArray(repoData?.topics) ? repoData.topics : [],
    lastPush: repoData?.pushed_at ?? null,
    sync: {
      status: error ? 'error' : 'ok',
      statusMessage: error ? error.message : null,
      fetchedAt: now
    }
  };
}

async function generate() {
  try {
    const projects = await readConfig();
    const results = await Promise.all(
      projects.map(async (project) => {
        try {
          const repoData = await fetchRepo(project.repo);
          return buildProject(project, repoData, null);
        } catch (error) {
          console.warn(`[warn] ${error.message}`);
          return buildProject(project, null, error);
        }
      })
    );

    const output = {
      generatedAt: new Date().toISOString(),
      source: 'github-api',
      projects: results
    };

    await writeFile(OUTPUT_PATH, JSON.stringify(output, null, 2) + '\n', 'utf8');

    console.log(`Wrote ${results.length} project entries to projects.json`);
  } catch (error) {
    console.error(`[error] ${error.message}`);
    process.exitCode = 1;
  }
}

generate();
