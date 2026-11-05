# 17. Compare with a recorded example

Open the included read-only example to see a complete source-to-deployment chain:

If Windows asks which app should open the `.html` file, select **Microsoft Edge > Just once**. No default-app change is required.

```powershell
. {
    $ErrorActionPreference = 'Stop'
    Start-Process (Join-Path (Get-Location).Path 'instructions\assets\development-evidence.html')
}
```

Follow the recorded run through its worker assignments, Sandbox snapshot, checks, accepted source files, image build, human approval, and application observation.

This example uses an older **v1 dataset**. Your lab uses **v2**. Compare the workflow, not the hashes or counts, and do not use its receipts to complete your own run.

The viewer shows a saved observation, not the application's current health. It is also available if you could not complete the live agent run.

## 17.1 Reflect on what you learned

- Why use separate worker Sandboxes and an independent integration workspace?
- Why is a network timeout not proof that the deny policy worked?
- Why must approval identify an exact image digest?

You have practiced coordinating agents in Foundry, isolating their work in Container Apps Sandboxes, and deploying a checked application to Container Apps Express.
