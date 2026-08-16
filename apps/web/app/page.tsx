"use client";
import Link from "next/link";
const cards = [
  ["T1 Contrast", "Why does white matter become bright?", "Uses: IR / GRE"],
  ["Dark Blood", "Suppress flowing blood while preserving vessel wall", "Uses: TSE"],
  ["Dixon", "Separate water and fat", "Uses: multi-echo GRE · seam only"],
  ["T2 Mapping", "Estimate transverse relaxation", "Uses: multi-echo SE"],
];
export default function Home() {
  return <section className="dashboard"><header><h1>Explore · Build · Resume</h1><p>Start with a clinical or physical question.</p></header>
    <div className="explore-grid">{cards.map(([title, question, uses]) =>
      <article key={title}><h2>{title}</h2><p>{question}</p><small>{uses}</small><Link href="/editor">Explore</Link></article>
    )}</div>
  </section>;
}
