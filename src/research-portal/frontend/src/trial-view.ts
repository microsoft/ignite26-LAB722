interface TrialFacet { phase: string; status: string }

export function summarizeTrials(trials: readonly TrialFacet[]) {
  function counts(field: keyof TrialFacet): [string, number][] {
    const values = new Map<string, number>();
    for (const trial of trials) values.set(trial[field], (values.get(trial[field]) ?? 0) + 1);
    return [...values].sort(([left], [right]) => left.localeCompare(right));
  }
  return { phases: counts("phase"), statuses: counts("status") };
}

export function filterTrials<T extends TrialFacet>(trials: readonly T[], phase: string, status: string): T[] {
  return trials.filter(trial => (!phase || trial.phase === phase) && (!status || trial.status === status));
}
