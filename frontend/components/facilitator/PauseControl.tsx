"use client";

import { Button } from "@/components/ui/Button";

export function PauseControl({
  paused,
  busy,
  onToggle,
}: {
  paused: boolean;
  busy: boolean;
  onToggle: () => void;
}) {
  return (
    <Button
      variant={paused ? "primary" : "secondary"}
      size="sm"
      data-testid="pause-button"
      loading={busy}
      onClick={onToggle}
    >
      {paused ? "Resume" : "Pause"}
    </Button>
  );
}
