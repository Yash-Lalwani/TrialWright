import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";

import "./home.css";

export const metadata: Metadata = {
  title: "Review clinical trial protocols before amendments happen",
  description:
    "Pre-Flight checks clinical trial protocols for missing sections, contradictions, participant burden and amendment risk, with page-linked evidence for every finding.",
};

const measuredResults = [
  { value: "9×", label: "the precision of a bare AI prompt", detail: "90% vs 10% on our held-out test set" },
  { value: "0", label: "ungrounded AI citations shown", detail: "60 rejected before reaching reviewers" },
  { value: "31s", label: "median review time", detail: "30.5 seconds across seven protocols" },
  { value: "<1¢", label: "median model cost per review", detail: "$0.0065 across the same seven" },
];

export default function HomePage() {
  return (
    <div className="landing">
      <section className="landing-hero" aria-labelledby="landing-title">
        <div className="landing-shell landing-hero-grid">
          <div className="landing-hero-copy">
            <p className="landing-eyebrow"><span aria-hidden="true" /> Clinical trial protocol review</p>
            <h1 id="landing-title">Find the gaps before they become amendments.</h1>
            <p className="landing-lede">
              Pre-Flight reads a protocol for missing requirements, contradictions and participant burden, then
              shows each finding beside the page that supports it.
            </p>
            <div className="landing-actions">
              <Link className="landing-primary" href="/protocol">
                Review a protocol <ArrowRight aria-hidden="true" size={18} />
              </Link>
              <a className="landing-secondary" href="#how-it-works">
                See how it works <span aria-hidden="true">↓</span>
              </a>
            </div>
            <p className="landing-hero-note">Built for protocol authors and review teams. The final decision stays with people.</p>
          </div>

          <div className="landing-problem" aria-label="Why protocol review matters">
            <p className="landing-panel-kicker">The problem</p>
            <p className="landing-problem-headline">Late protocol changes cost time and money.</p>
            <div className="landing-problem-stat">
              <strong>45%</strong>
              <span>of substantial amendments were judged avoidable</span>
            </div>
            <div className="landing-problem-stat">
              <strong>$535K</strong>
              <span>median direct cost of one Phase III amendment</span>
            </div>
            <a href="https://pubmed.ncbi.nlm.nih.gov/30227022/" target="_blank" rel="noreferrer">
              Tufts CSDD / Getz et al., 2016 <ArrowUpRight aria-hidden="true" size={14} />
            </a>
          </div>
        </div>
      </section>

      <section className="landing-results landing-shell" aria-labelledby="results-title">
        <div className="landing-section-heading">
          <p className="landing-section-kicker">Measured performance</p>
          <h2 id="results-title">A review you can trace.</h2>
          <p>Measured on seven held-out protocols with 65 injected errors. The live demo protocol is 134 pages. <a href="https://github.com/Yash-Lalwani/TrialWright/blob/main/docs/RESULTS.md" target="_blank" rel="noreferrer">See the evaluation <ArrowUpRight aria-hidden="true" size={14} /></a></p>
        </div>
        <div className="landing-metrics">
          {measuredResults.map((item) => (
            <div className="landing-metric" key={item.value}>
              <strong>{item.value}</strong>
              <span>{item.label}</span>
              <small>{item.detail}</small>
            </div>
          ))}
        </div>
        <div className="landing-proof" aria-label="Additional results">
          <p><strong>25 issues resolved</strong><span>in one demo revision, with the score moving from 70 to 84</span></p>
          <p><strong>91% fewer false alarms</strong><span>after rule fixes on a real amended protocol</span></p>
          <p><strong>200 trial histories</strong><span>in an exploratory check of an eligibility outlier signal</span></p>
        </div>
      </section>

      <section className="landing-method" id="how-it-works" aria-labelledby="method-title">
        <div className="landing-shell landing-method-grid">
          <div className="landing-section-heading">
            <p className="landing-section-kicker">What we built</p>
            <h2 id="method-title">From a dense PDF to a useful review.</h2>
            <p>Rules and four specialist AI reviewers work together. A verifier checks every AI quote against its cited page before it appears. Confidential mode makes no model calls.</p>
            <Link href="/protocol">Open the review workspace <ArrowRight aria-hidden="true" size={16} /></Link>
          </div>
          <ol className="landing-steps">
            <li><span>01</span><div><h3>Map the protocol</h3><p>Parse the PDF, its schedule and key trial details against ICH M11 and SPIRIT 2025.</p></div></li>
            <li><span>02</span><div><h3>Check the logic</h3><p>Find missing sections, contradictions, visit conflicts and burden outliers against peer trials.</p></div></li>
            <li><span>03</span><div><h3>Review the evidence</h3><p>Open each finding on its source page, accept or reject it, then compare a revision.</p></div></li>
          </ol>
        </div>
      </section>

      <section className="landing-architecture landing-shell" aria-labelledby="architecture-title">
        <div className="landing-section-heading landing-architecture-heading">
          <div>
            <p className="landing-section-kicker">Explore the system</p>
            <h2 id="architecture-title">How Pre-Flight works together.</h2>
          </div>
          <a href="/architecture.html?theme=light" target="_blank" rel="noreferrer">
            Open full diagram <ArrowUpRight aria-hidden="true" size={16} />
          </a>
        </div>
        <div className="landing-diagram-frame">
          <iframe
            title="Interactive Pre-Flight architecture diagram"
            src="/architecture.html?theme=light"
            loading="lazy"
          />
        </div>
      </section>

      <footer className="landing-footer">
        <div className="landing-shell">
          <p>Pre-Flight reviews protocols before teams commit to a trial design.</p>
          <Link href="/protocol">Start a review <ArrowRight aria-hidden="true" size={16} /></Link>
        </div>
      </footer>
    </div>
  );
}
