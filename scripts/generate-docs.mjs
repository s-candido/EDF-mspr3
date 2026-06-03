import 'dotenv/config';
import fs from 'node:fs/promises';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import fg from 'fast-glob';
import YAML from 'yaml';
import { minimatch } from 'minimatch';
import { GoogleGenAI } from '@google/genai';

const execFileAsync = promisify(execFile);
const ROOT = process.cwd();

const GENERATION_MODE = process.env.GENERATION_MODE || 'generate'; // generate | improve | update
const DOCUSAURUS_DIR = process.env.DOCUSAURUS_DIR || 'docs';
const STATE_PATH = '.ai-docs/output/generation-state.json';
const PAGES_PATH = '.ai-docs/pages.json';
const DOC_MAP_PATH = '.ai-docs/doc-map.yml';

const GEMINI_MODELS = [
  process.env.GEMINI_PRIMARY_MODEL || 'gemini-3.1-flash-lite',
  process.env.GEMINI_REVIEW_MODEL || 'gemini-2.5-flash',
  process.env.GEMINI_FALLBACK_MODEL_1 || 'gemma-4-31b',
  process.env.GEMINI_FALLBACK_MODEL_2 || 'gemma-4-26b',
].filter(Boolean);

const INVENTORY_MODEL = process.env.GEMINI_INVENTORY_MODEL || GEMINI_MODELS[0];
const PAGE_MODEL = process.env.GEMINI_PRIMARY_MODEL || GEMINI_MODELS[0];
const REVIEW_MODEL = process.env.GEMINI_REVIEW_MODEL || GEMINI_MODELS[0];

const MAX_PAGES_PER_RUN = Number(process.env.MAX_PAGES_PER_RUN || 3);
const DELAY_BETWEEN_PAGES_MS = Number(process.env.DELAY_BETWEEN_PAGES_MS || 8000);
const SKIP_GENERATED_PAGES = String(process.env.SKIP_GENERATED_PAGES || 'true') === 'true';
const RESET_GENERATION_STATE = String(process.env.RESET_GENERATION_STATE || 'false') === 'true';
const RUN_DOCUSAURUS_BUILD = String(process.env.RUN_DOCUSAURUS_BUILD || 'false') === 'true';
const GIT_DIFF_BASE = process.env.GIT_DIFF_BASE || 'HEAD~1';

const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY,
});

const includedPatterns = [
  'README.md',
  'ChangeLog.md',
  'UsageExamples.md',
  'dags.md',
  'dags_fr.md',
  'deploy.md',
  'docker-compose.yml',
  'requirement.txt',
  'requirements.txt',
  '.github/workflows/*.{yml,yaml}',
  'dags/**/*.{py,md,yml,yaml,json,sql}',
  'src/**/*.{py,md,yml,yaml,json,sql}',
  'scripts/**/*.{py,js,mjs,sh,ps1,md}',
  'notebooks/**/*.{ipynb,md}',
  'infra/**/*.{yml,yaml,tf,sh,md}',
  'k8s/**/*.{yml,yaml,md}',
  'docker/**/*.{Dockerfile,dockerfile,sh,yml,yaml,md}',
  'env_files/**/*.example',
  'env_files/**/example*',
];

const ignoredPatterns = [
  '**/node_modules/**',
  '**/.next/**',
  '**/dist/**',
  '**/build/**',
  '**/.git/**',
  '**/coverage/**',
  '**/*.lock',
  '**/package-lock.json',
  '**/pnpm-lock.yaml',
  '**/yarn.lock',
  '**/__pycache__/**',
  '**/*.pyc',
  '**/.ipynb_checkpoints/**',
  '**/.cache.sqlite',
  'docs/.docusaurus/**',
  'docs/build/**',
  'docs/docs/**',
  '.ai-docs/output/**',
  '.env',
  '**/.env',
  '**/*.env',
  'env_files/.env',
  'env_files/secrets.env',
];

async function readText(filePath) {
  try {
    return await fs.readFile(filePath, 'utf8');
  } catch {
    return '';
  }
}

async function writeDoc(filePath, content) {
  const absolutePath = path.join(ROOT, filePath);
  await fs.mkdir(path.dirname(absolutePath), { recursive: true });
  await fs.writeFile(absolutePath, content, 'utf8');
}

async function readJson(filePath, fallback = null) {
  try {
    const absolutePath = path.join(ROOT, filePath);
    const content = await fs.readFile(absolutePath, 'utf8');
    return JSON.parse(content);
  } catch (error) {
    if (fallback !== null) return fallback;
    throw error;
  }
}

async function readYaml(filePath, fallback = null) {
  try {
    const absolutePath = path.join(ROOT, filePath);
    const content = await fs.readFile(absolutePath, 'utf8');
    return YAML.parse(content);
  } catch (error) {
    if (fallback !== null) return fallback;
    throw error;
  }
}

async function loadPrompt(name) {
  const promptPath = path.join(ROOT, '.ai-docs', 'prompts', name);
  const content = await readText(promptPath);

  if (!content.trim()) {
    throw new Error(`Prompt file is missing or empty: ${promptPath}`);
  }

  return content;
}

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function cleanMarkdown(content) {
  let cleaned = content.trim();
  cleaned = cleaned.replace(/^```markdown\s*/i, '');
  cleaned = cleaned.replace(/^```\s*/i, '');
  cleaned = cleaned.replace(/```\s*$/i, '');
  return cleaned.trim();
}

function isQuotaOrRetryableError(error) {
  const message = String(error?.message || error || '').toLowerCase();

  return (
    message.includes('429') ||
    message.includes('quota') ||
    message.includes('rate limit') ||
    message.includes('resource exhausted') ||
    message.includes('too many requests') ||
    message.includes('exceeded') ||
    message.includes('overloaded') ||
    message.includes('temporarily unavailable') ||
    message.includes('503') ||
    message.includes('500')
  );
}

async function askGemini({ systemPrompt, userPrompt, preferredModel }) {
  if (!process.env.GEMINI_API_KEY) {
    throw new Error('GEMINI_API_KEY is missing. Add it to your .env file.');
  }

  const modelsToTry = preferredModel
    ? [preferredModel, ...GEMINI_MODELS.filter((model) => model !== preferredModel)]
    : GEMINI_MODELS;

  const errors = [];

  for (const model of modelsToTry) {
    try {
      console.log(`Trying Gemini model: ${model}`);

      const response = await ai.models.generateContent({
        model,
        contents: [
          {
            role: 'user',
            parts: [{ text: `${systemPrompt}\n\n${userPrompt}` }],
          },
        ],
      });

      const text = response.text;

      if (!text || !text.trim()) {
        throw new Error(`Gemini model ${model} returned an empty response.`);
      }

      console.log(`Gemini model succeeded: ${model}`);
      return cleanMarkdown(text);
    } catch (error) {
      const message = error?.message || String(error);
      errors.push(`- ${model}: ${message}`);

      console.warn(`Gemini model failed: ${model}`);
      console.warn(message);

      if (isQuotaOrRetryableError(error)) {
        console.warn('Quota/rate-limit or temporary error detected. Trying next model...');
      } else {
        console.warn('Non-quota error detected. Trying next model anyway...');
      }

      await sleep(3000);
    }
  }

  throw new Error(`All Gemini models failed:\n${errors.join('\n')}`);
}

async function collectRepoContext() {
  const files = await fg(includedPatterns, {
    cwd: ROOT,
    ignore: ignoredPatterns,
    dot: true,
    onlyFiles: true,
  });

  const selected = [];

  for (const file of files.slice(0, 160)) {
    const absolutePath = path.join(ROOT, file);
    const content = await readText(absolutePath);

    if (!content.trim()) continue;

    selected.push({
      path: file,
      content: content.slice(0, 16000),
    });
  }

  return selected;
}

function formatRepoContext(repoFiles) {
  return repoFiles
    .map((file) => `--- FILE: ${file.path} ---\n${file.content}`)
    .join('\n\n');
}

function buildDiagramInstruction(page) {
  if (!page.mustIncludeDiagrams || page.mustIncludeDiagrams.length === 0) {
    return `
La page peut ne pas inclure de diagramme si ce n’est pas pertinent.
Si un diagramme aide la compréhension, utilise Mermaid avec ce format exact :

\`\`\`mermaid
flowchart TD
  A[Étape A] --> B[Étape B]
\`\`\`
`;
  }

  return `
La page doit inclure au moins un diagramme Mermaid.

Types de diagrammes attendus :
${page.mustIncludeDiagrams.map((diagram) => `- ${diagram}`).join('\n')}

Format obligatoire :

\`\`\`mermaid
flowchart TD
  A[Étape A] --> B[Étape B]
\`\`\`

Règles pour Mermaid :
- Le bloc doit commencer exactement par \`\`\`mermaid.
- Ne jamais utiliser un bloc \`\`\` simple pour Mermaid.
- Ne jamais indenter le diagramme avec 4 espaces.
- Diagramme simple et lisible.
- 4 à 12 nœuds maximum.
- Syntaxe compatible Docusaurus Mermaid.
- Ne pas créer de diagramme trop dense.
`;
}

function buildPagePrompt({ pagePrompt, page, inventory, existingContent }) {
  const diagramInstruction = buildDiagramInstruction(page);
  const validationSection = page.type === 'functional' ? '## Hypothèses à valider' : '## À vérifier manuellement';

  return `${pagePrompt}

Tu dois générer ou améliorer la page suivante.

Mode de génération : ${GENERATION_MODE}

Chemin :
${page.outputPath}

Titre :
${page.title}

Description :
${page.description}

Instructions sur les diagrammes :
${diagramInstruction}

Contenu existant de la page :
${existingContent || 'Aucun contenu existant.'}

Objectif :
Produire une page complète, claire, visuelle et lisible pour Docusaurus.

Contraintes obligatoires :
- Commence directement par "# ${page.title}".
- Ne mets pas de bloc \`\`\`markdown autour de toute la réponse.
- Évite absolument les gros pavés.
- Aucun paragraphe ne doit dépasser 8 lignes.
- Utilise des tableaux dès qu’il y a plusieurs éléments comparables.
- Utilise des listes à puces.
- Utilise des encadrés Docusaurus quand c’est utile.
- Utilise Mermaid quand demandé.
- Tout diagramme Mermaid doit être dans un bloc commençant exactement par \`\`\`mermaid.
- Ne jamais mettre un diagramme Mermaid dans un bloc \`\`\` simple.
- Ajoute une section "Sources utilisées".
- Ajoute une section "${validationSection.replace('## ', '')}".
- N’invente pas d’information absente du repository.
- Distingue clairement : confirmé par le code, documenté dans le README, déduit, à vérifier.
- Ne recopie jamais de secret ou de valeur sensible.

Structure recommandée :
# ${page.title}

## Résumé

## Vue d’ensemble

## Schéma

## Détails

## Tableau de synthèse

## Points d’attention

${validationSection}

## Sources utilisées

Inventaire du repository :

${inventory}`;
}

async function generatePage({ systemPrompt, technicalPrompt, functionalPrompt, inventory, page }) {
  console.log(`Generating ${page.outputPath}...`);

  const pagePrompt = page.type === 'functional' ? functionalPrompt : technicalPrompt;
  const existingContent = await readText(path.join(ROOT, page.outputPath));

  const content = await askGemini({
    systemPrompt,
    userPrompt: buildPagePrompt({ pagePrompt, page, inventory, existingContent }),
    preferredModel: PAGE_MODEL,
  });

  await writeDoc(page.outputPath, content);

  return {
    path: page.outputPath,
    title: page.title,
    type: page.type,
    content,
  };
}

function validatePageConfig(page) {
  if (!page.outputPath || !page.type || !page.title || !page.description) {
    throw new Error(`Invalid page configuration in ${PAGES_PATH}: ${JSON.stringify(page)}`);
  }

  if (!['technical', 'functional', 'meta'].includes(page.type)) {
    throw new Error(`Invalid page type for ${page.outputPath}: ${page.type}`);
  }
}

function chunkGeneratedPagesForReview(generatedPages) {
  return generatedPages
    .map((page) => `--- ${page.path} ---\n${page.content.slice(0, 10000)}`)
    .join('\n\n');
}

async function readGenerationState() {
  if (RESET_GENERATION_STATE) {
    return {
      generatedPages: [],
      updatedPages: [],
      improvedPages: [],
      lastRun: null,
    };
  }

  return readJson(STATE_PATH, {
    generatedPages: [],
    updatedPages: [],
    improvedPages: [],
    lastRun: null,
  });
}

async function writeGenerationState(state) {
  await writeDoc(STATE_PATH, JSON.stringify(state, null, 2));
}

function getAlreadyGeneratedPaths(state) {
  return new Set((state.generatedPages || []).map((entry) => (typeof entry === 'string' ? entry : entry.path)));
}

async function getGitChangedFiles() {
  const commands = [
    ['git', ['diff', '--name-only', `${GIT_DIFF_BASE}..HEAD`]],
    ['git', ['diff', '--name-only', 'HEAD']],
    ['git', ['diff', '--name-only', '--cached']],
  ];

  const changed = new Set();

  for (const [cmd, args] of commands) {
    try {
      const { stdout } = await execFileAsync(cmd, args, { cwd: ROOT });
      stdout
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean)
        .forEach((file) => changed.add(file.replace(/\\/g, '/')));
    } catch {
      // Ignore git errors so the script can still run outside a full git context.
    }
  }

  return [...changed];
}

function docsFromChangedFiles(changedFiles, docMap) {
  const docs = new Set();
  const rules = docMap?.rules || [];

  for (const changedFile of changedFiles) {
    for (const rule of rules) {
      const codePatterns = rule.code || [];
      const docPaths = rule.docs || [];

      const matchesRule = codePatterns.some((pattern) =>
        minimatch(changedFile, pattern, { dot: true, matchBase: false })
      );

      if (matchesRule) {
        docPaths.forEach((doc) => docs.add(doc));
      }
    }
  }

  return [...docs];
}

function inferPageConfigFromPath(outputPath) {
  const filename = path.basename(outputPath, path.extname(outputPath));
  const title = filename
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');

  const type = outputPath.includes('/functional/') ? 'functional' : outputPath.includes('/meta/') ? 'meta' : 'technical';

  return {
    outputPath,
    type,
    title,
    description: `Mettre à jour la page ${title} à partir des changements détectés dans le repository.`,
    mustIncludeDiagrams: type === 'technical' ? ['flowchart'] : [],
  };
}

function resolvePagesForMode({ pagesConfig, state, changedFiles, docMap }) {
  const enabledPages = pagesConfig.filter((page) => page.enabled !== false);

  for (const page of enabledPages) {
    validatePageConfig(page);
  }

  if (GENERATION_MODE === 'update') {
    const impactedDocPaths = docsFromChangedFiles(changedFiles, docMap);
    const pagesByPath = new Map(enabledPages.map((page) => [page.outputPath, page]));

    return impactedDocPaths.map((docPath) => pagesByPath.get(docPath) || inferPageConfigFromPath(docPath));
  }

  if (GENERATION_MODE === 'improve') {
    return enabledPages;
  }

  const alreadyGenerated = getAlreadyGeneratedPaths(state);

  if (!SKIP_GENERATED_PAGES) {
    return enabledPages;
  }

  return enabledPages.filter((page) => !alreadyGenerated.has(page.outputPath));
}

async function runDocusaurusBuild() {
  if (!RUN_DOCUSAURUS_BUILD) return null;

  console.log('Running Docusaurus build...');

  const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';

  try {
    const { stdout, stderr } = await execFileAsync(npmCmd, ['run', 'build'], {
      cwd: path.join(ROOT, DOCUSAURUS_DIR),
      maxBuffer: 1024 * 1024 * 20,
    });

    console.log(stdout);
    if (stderr) console.warn(stderr);

    return {
      ok: true,
      stdout,
      stderr,
    };
  } catch (error) {
    const stdout = error?.stdout || '';
    const stderr = error?.stderr || error?.message || '';

    console.error(stdout);
    console.error(stderr);

    return {
      ok: false,
      stdout,
      stderr,
    };
  }
}

function updateStateWithGeneratedPages(state, generatedPages) {
  const now = new Date().toISOString();
  state.lastRun = now;

  const targetKey =
    GENERATION_MODE === 'update'
      ? 'updatedPages'
      : GENERATION_MODE === 'improve'
        ? 'improvedPages'
        : 'generatedPages';

  if (!Array.isArray(state[targetKey])) state[targetKey] = [];

  const existingPaths = new Set(state[targetKey].map((entry) => (typeof entry === 'string' ? entry : entry.path)));

  for (const page of generatedPages) {
    if (!existingPaths.has(page.path)) {
      state[targetKey].push({
        path: page.path,
        title: page.title,
        mode: GENERATION_MODE,
        generatedAt: now,
      });
    }
  }

  return state;
}

async function main() {
  console.log('Starting AI documentation generation...');
  console.log(`Mode: ${GENERATION_MODE}`);
  console.log(`Available Gemini models: ${GEMINI_MODELS.join(', ')}`);
  console.log(`Inventory model: ${INVENTORY_MODEL}`);
  console.log(`Page model: ${PAGE_MODEL}`);
  console.log(`Review model: ${REVIEW_MODEL}`);
  console.log(`MAX_PAGES_PER_RUN: ${MAX_PAGES_PER_RUN}`);
  console.log(`DELAY_BETWEEN_PAGES_MS: ${DELAY_BETWEEN_PAGES_MS}`);

  const systemPrompt = await loadPrompt('system.md');
  const inventoryPrompt = await loadPrompt('inventory.md');
  const technicalPrompt = await loadPrompt('technical-docs.md');
  const functionalPrompt = await loadPrompt('functional-docs.md');
  const reviewPrompt = await loadPrompt('review.md');

  const pagesConfig = await readJson(PAGES_PATH);
  const docMap = await readYaml(DOC_MAP_PATH, { rules: [] });
  const state = await readGenerationState();

  if (!Array.isArray(pagesConfig) || pagesConfig.length === 0) {
    throw new Error(`${PAGES_PATH} is missing, empty, or invalid.`);
  }

  const changedFiles = GENERATION_MODE === 'update' ? await getGitChangedFiles() : [];

  if (GENERATION_MODE === 'update') {
    console.log(`Changed files detected: ${changedFiles.length}`);
    changedFiles.forEach((file) => console.log(`- ${file}`));
  }

  const candidatePages = resolvePagesForMode({ pagesConfig, state, changedFiles, docMap });
  const pagesToGenerate = candidatePages.slice(0, MAX_PAGES_PER_RUN);

  console.log(`Configured pages: ${pagesConfig.length}`);
  console.log(`Candidate pages for mode ${GENERATION_MODE}: ${candidatePages.length}`);
  console.log(`Pages generated in this run: ${pagesToGenerate.length}`);

  if (pagesToGenerate.length === 0) {
    console.log('No pages to generate for this run.');
    await writeGenerationState(state);
    return;
  }

  const repoFiles = await collectRepoContext();
  const repoContext = formatRepoContext(repoFiles);

  console.log(`Collected ${repoFiles.length} repository files.`);

  if (repoFiles.length === 0) {
    throw new Error('No repository files were collected. Check includedPatterns and ignoredPatterns.');
  }

  console.log('Generating repository inventory...');

  const updateContext =
    GENERATION_MODE === 'update'
      ? `\nFichiers modifiés détectés par Git :\n${changedFiles.map((file) => `- ${file}`).join('\n')}\n`
      : '';

  const inventory = await askGemini({
    systemPrompt,
    preferredModel: INVENTORY_MODEL,
    userPrompt: `${inventoryPrompt}

Contexte important :
Le repository EDF-MSPR3 est un projet MLOps autour de la consommation énergétique.
Il utilise notamment Docker Compose, Airflow, MLflow, PostgreSQL, des scripts Python et des notebooks.
Tu dois vérifier ces informations à partir des fichiers fournis ci-dessous.

Mode de génération : ${GENERATION_MODE}
${updateContext}
Important :
L’inventaire doit être factuel, structuré et utilisable pour générer les pages demandées.
Il doit distinguer ce qui est confirmé par le code, documenté dans le README, déduit ou à vérifier.

Voici les fichiers du repository :

${repoContext}`,
  });

  await writeDoc('.ai-docs/output/repo-inventory.md', inventory);

  const generatedPages = [];

  for (const page of pagesToGenerate) {
    const generatedPage = await generatePage({
      systemPrompt,
      technicalPrompt,
      functionalPrompt,
      inventory,
      page,
    });

    generatedPages.push(generatedPage);

    if (DELAY_BETWEEN_PAGES_MS > 0) {
      console.log(`Waiting ${DELAY_BETWEEN_PAGES_MS}ms before next page...`);
      await sleep(DELAY_BETWEEN_PAGES_MS);
    }
  }

  console.log('Reviewing generated documentation...');

  const generatedDocsForReview = chunkGeneratedPagesForReview(generatedPages);

  const review = await askGemini({
    systemPrompt,
    preferredModel: REVIEW_MODEL,
    userPrompt: `${reviewPrompt}

Voici la documentation générée pendant ce run :

${generatedDocsForReview}

Retourne un rapport de relecture en Markdown.

Le rapport doit contenir :
- niveau de confiance global ;
- problèmes critiques ;
- problèmes de lisibilité ;
- risques d’hallucination ;
- pages qui manquent de schémas ;
- pages qui manquent de tableaux ;
- informations à vérifier manuellement ;
- fichiers qui devraient être améliorés ensuite ;
- validation Docusaurus / Mermaid.`,
  });

  const buildResult = await runDocusaurusBuild();
  const updatedState = updateStateWithGeneratedPages(state, generatedPages);
  await writeGenerationState(updatedState);

  const report = `# Rapport de génération IA

## Mode

\`${GENERATION_MODE}\`

## Modèles configurés

- Inventaire : \`${INVENTORY_MODEL}\`
- Génération pages : \`${PAGE_MODEL}\`
- Relecture : \`${REVIEW_MODEL}\`
- Fallbacks disponibles : ${GEMINI_MODELS.map((model) => `\`${model}\``).join(', ')}

## Paramètres du run

- Pages configurées : ${pagesConfig.length}
- Pages candidates : ${candidatePages.length}
- Pages générées dans ce run : ${generatedPages.length}
- Délai entre pages : ${DELAY_BETWEEN_PAGES_MS} ms
- Build Docusaurus demandé : ${RUN_DOCUSAURUS_BUILD ? 'oui' : 'non'}
- Build Docusaurus : ${buildResult ? (buildResult.ok ? 'OK' : 'ÉCHEC') : 'non exécuté'}

## Fichiers modifiés détectés

${changedFiles.length ? changedFiles.map((file) => `- \`${file}\``).join('\n') : 'Aucun fichier modifié listé pour ce mode.'}

## Fichiers analysés

${repoFiles.map((file) => `- \`${file.path}\``).join('\n')}

## Pages générées

${generatedPages.map((page) => `- \`${page.path}\` — ${page.title} (${page.type})`).join('\n')}

## Rapport de relecture

${review}

## Résultat du build Docusaurus

${buildResult ? `Statut : ${buildResult.ok ? 'OK' : 'ÉCHEC'}\n\n\`\`\`text\n${(buildResult.stderr || buildResult.stdout || '').slice(0, 12000)}\n\`\`\`` : 'Build non exécuté.'}
`;

  await writeDoc('docs/docs/meta/ai-generation-report.md', report);

  console.log('Done.');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
