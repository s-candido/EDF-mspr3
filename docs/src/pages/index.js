import React from 'react';
import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './index.module.css';

const sections = [
  {
    title: 'Documentation fonctionnelle',
    description:
      'Comprendre l’objectif métier du projet, les flux de données, les fonctionnalités et les parcours d’utilisation.',
    link: '/docs/functional/overview',
    cta: 'Voir la doc fonctionnelle',
  },
  {
    title: 'Documentation technique',
    description:
      'Explorer l’architecture MLOps, Docker Compose, Airflow, MLflow, PostgreSQL et les pipelines Python.',
    link: '/docs/technical/architecture',
    cta: 'Voir la doc technique',
  },
  {
    title: 'Pipelines & orchestration',
    description:
      'Comprendre le rôle des DAGs Airflow, des traitements batch et du suivi des modèles.',
    link: '/docs/technical/airflow',
    cta: 'Voir Airflow',
  },
  {
    title: 'Suivi IA',
    description:
      'Consulter le rapport de génération automatique produit par l’agent IA de documentation.',
    link: '/docs/meta/ai-generation-report',
    cta: 'Voir le rapport IA',
  },
];

function HomepageHeader() {
  return (
    <header className={styles.hero}>
      <div className="container">
        <div className={styles.heroContent}>
          <div className={styles.badge}>EDF-MSPR3 · Documentation IA</div>

          <Heading as="h1" className={styles.heroTitle}>
            Documentation technique et fonctionnelle du projet EDF-MSPR3
          </Heading>

          <p className={styles.heroSubtitle}>
            Un espace centralisé pour comprendre l’architecture MLOps, les flux
            de données, les pipelines Airflow, le tracking MLflow et les usages
            fonctionnels du projet.
          </p>

          <div className={styles.heroActions}>
            <Link className="button button--primary button--lg" to="/docs/intro">
              Commencer
            </Link>
            <Link className="button button--secondary button--lg" to="/docs/technical/architecture">
              Architecture
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
}

function SectionCards() {
  return (
    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2">Explorer la documentation</Heading>
          <p>
            Accède rapidement aux parties principales de la documentation générée
            et maintenue avec l’aide d’un agent IA.
          </p>
        </div>

        <div className={styles.cardGrid}>
          {sections.map((section) => (
            <article className={styles.card} key={section.title}>
              <h3>{section.title}</h3>
              <p>{section.description}</p>
              <Link to={section.link}>{section.cta} →</Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function WorkflowSection() {
  return (
    <section className={styles.workflow}>
      <div className="container">
        <div className={styles.workflowBox}>
          <div>
            <Heading as="h2">Cycle de vie documentaire</Heading>
            <p>
              La documentation est générée en Markdown, relue dans Obsidian,
              versionnée avec GitHub et publiée via Docusaurus.
            </p>
          </div>

          <div className={styles.steps}>
            <div className={styles.step}>Repo GitHub</div>
            <div className={styles.arrow}>→</div>
            <div className={styles.step}>Agent IA</div>
            <div className={styles.arrow}>→</div>
            <div className={styles.step}>Markdown</div>
            <div className={styles.arrow}>→</div>
            <div className={styles.step}>Docusaurus</div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function Home() {
  return (
    <Layout
      title="Documentation EDF-MSPR3"
      description="Documentation technique et fonctionnelle du projet EDF-MSPR3"
    >
      <HomepageHeader />
      <main>
        <SectionCards />
        <WorkflowSection />
      </main>
    </Layout>
  );
}