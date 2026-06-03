// @ts-check

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/**
 * Creating a sidebar enables you to:
 - create an ordered group of docs
 - render a sidebar for each doc of that group
 - provide next/previous navigation

 The sidebars can be generated from the filesystem, or explicitly defined here.

 Create as many sidebars as you want.

 @type {import('@docusaurus/plugin-content-docs').SidebarsConfig}
 */
const sidebars = {
docsSidebar: [
    'intro',
    {
      type: 'category',
      label: 'Documentation fonctionnelle',
      items: [
        'functional/overview',
        'functional/data-flow',
        'functional/features',
        'functional/user-journeys',
        'functional/user-roles',
        'functional/permissions',
        'functional/business-rules',
        'functional/glossary',
      ],
    },
    {
      type: 'category',
      label: 'Documentation technique',
      items: [
        'technical/architecture',
        'technical/installation',
        'technical/configuration',
        'technical/environment-variables',
        'technical/docker-compose',
        'technical/airflow',
        'technical/mlflow',
        'technical/database',
        'technical/pipelines',
        'technical/scripts-python',
        'technical/backend',
        'technical/services',
        'technical/api',
        'technical/authentication',
        'technical/frontend',
        'technical/notebooks',
        'technical/deployment',
        'technical/testing',
        'technical/troubleshooting',
      ],
    },
    {
      type: 'category',
      label: 'Architecture Decisions',
      items: ['adr/initial-architecture'],
    },
    {
      type: 'category',
      label: 'Suivi IA',
      items: ['meta/ai-generation-report'],
    },
  ],
};


export default sidebars;
