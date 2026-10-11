"use client";

import { Check, X } from "lucide-react";
import { useId, useState } from "react";

import { errorMessage } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { useDecision } from "@/lib/queries";
import type { Issue } from "@/lib/types";
import { cn } from "@/lib/utils";

/** The reviewer is not authenticated in this build; every decision is recorded under this name. */
const REVIEWER = "reviewer";

/**
 * E2: accept or reject one issue, with an optional note. The list updates at once and the
 * score follows from the server's reply. Every decision lands in the audit tab.
 */
export function DecisionPanel({ runId, issue }: { runId: string; issue: Issue }) {
  const decide = useDecision(runId);
  const noteId = useId();
  const [note, setNote] = useState("");
  const decided = issue.status !== "open";

  const submit = (decision: "accepted" | "rejected") => {
    decide.mutate({ issueId: issue.id, decision, note: note.trim(), user: REVIEWER }, { onSuccess: () => setNote("") });
  };

  return (
    <div className="rounded-md border bg-muted/40 p-2.5">
      <label htmlFor={noteId} className="text-xs font-semibold">
        {decided ? `Marked ${issue.status}. Change your decision` : "Your decision"}
      </label>
      <textarea
        id={noteId}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
        maxLength={500}
        placeholder="Optional note for the audit trail"
        className="mt-1.5 w-full resize-none rounded-md border bg-card px-2.5 py-1.5 text-sm placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
      />
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          data-decision="accepted"
          disabled={decide.isPending}
          variant={issue.status === "accepted" ? "default" : "outline"}
          aria-pressed={issue.status === "accepted"}
          onClick={() => submit("accepted")}
        >
          <Check aria-hidden /> {issue.status === "accepted" ? "Accepted" : "Accept"}
        </Button>
        <Button
          size="sm"
          data-decision="rejected"
          disabled={decide.isPending}
          variant={issue.status === "rejected" ? "default" : "outline"}
          aria-pressed={issue.status === "rejected"}
          onClick={() => submit("rejected")}
        >
          <X aria-hidden /> {issue.status === "rejected" ? "Rejected" : "Reject"}
        </Button>
        <span className={cn("text-xs text-muted-foreground", decide.isError && "text-sev-critical")} role="status" aria-live="polite">
          {decide.isPending ? "Saving…" : decide.isError ? `Not saved: ${errorMessage(decide.error)}` : ""}
        </span>
      </div>
      <p className="mt-1.5 text-xs text-muted-foreground">Accepting a fix removes its points from the score. Rejecting keeps them.</p>
    </div>
  );
}
