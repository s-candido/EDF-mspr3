// @ts-check
import { themes as prismThemes } from 'prism-react-renderer';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'EDF-MSPR3 Documentation',
  tagline: 'Documentation technique et fonctionnelle du projet EDF-MSPR3',
  favicon: 'img/favicon.ico',

  url: 'https://s-candido.github.io',
  baseUrl: '/EDF-mspr3/',

  organizationName: 's-candido',
  projectName: 'EDF-mspr3',

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

  markdown: {
    mermaid: true,
  },

  themes: ['@docusaurus/theme-mermaid'],

  i18n: {
    defaultLocale: 'fr',
    locales: ['fr'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.js',
          editUrl: 'https://github.com/s-candido/EDF-mspr3/tree/main/docs/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      },
    ],
  ],

  themeConfig: {
    image: 'img/docusaurus-social-card.jpg',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'EDF-MSPR3',
      logo: {
        alt: 'EDF-MSPR3 Logo',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          label: 'Documentation',
          position: 'left',
        },
        {
          href: 'https://github.com/s-candido/EDF-mspr3',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Documentation',
          items: [
            {
              label: 'Introduction',
              to: '/docs/intro',
            },
          ],
        },
        {
          title: 'Projet',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/s-candido/EDF-mspr3',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} EDF-MSPR3.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  },
};

export default config;