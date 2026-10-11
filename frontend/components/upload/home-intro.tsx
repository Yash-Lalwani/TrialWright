const STEPS = [
  {
    title: "Upload the protocol PDF",
    body: "Optionally add its NCT identifier to compare against the ClinicalTrials.gov record.",
  },
  {
    title: "Pre-Flight runs the checks",
    body: "Rule checks, plus four AI reviewers in a full review. An AI finding is kept only if its quote is found on the cited page.",
  },
  {
    title: "Review findings beside the document",
    body: "Each finding opens its evidence, highlighted on the exact page of the PDF.",
  },
];

/** First screen: what Pre-Flight does and how a review flows, before the upload form. */
export function HomeIntro() {
  return (
    <section aria-labelledby="intro-heading" className="border-b bg-card">
      <div className="mx-auto grid w-full max-w-6xl gap-8 px-4 py-8 md:px-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:gap-14 lg:py-10">
        <div className="max-w-xl">
          <h1 id="intro-heading" className="text-[28px] leading-[1.2] font-semibold tracking-tight text-balance text-foreground sm:text-[32px]">
            Find protocol problems before they become amendments.
          </h1>
          <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">
            Pre-Flight checks a clinical trial protocol for completeness against ICH M11 and SPIRIT, internal
            consistency, participant burden and amendment risk. Every finding links to the text it comes from.
          </p>
        </div>

        <ol className="relative space-y-4 self-center">
          {STEPS.map((step, i) => (
            <li key={step.title} className="relative flex gap-3.5">
              {i < STEPS.length - 1 && (
                <span aria-hidden className="absolute top-8 bottom-[-1rem] left-[13px] w-px bg-border" />
              )}
              <span className="relative flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-[13px] font-semibold text-primary-foreground tabular">
                {i + 1}
              </span>
              <span className="min-w-0 pt-0.5">
                <span className="block text-sm font-semibold">{step.title}</span>
                <span className="mt-0.5 block text-[13px] leading-relaxed text-muted-foreground">{step.body}</span>
              </span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
