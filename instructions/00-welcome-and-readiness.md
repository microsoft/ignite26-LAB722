# Segment 0 - Welcome and readiness (5 minutes)

Review the Caldova request, confirm the automated deployment status, and identify the data and application versions used in the lab.

## Why this segment matters

Every worker must start from the same source, data, and acceptance criteria. The readiness check prevents later results from being compared across different versions.

## Services used

- Skillable lab environment for identity and deployment startup
- GitHub for the feature request and source version
- Azure Monitor for deployment readiness

## Learning objectives

- Identify the lab's trust boundaries and definition of done.
- Confirm that the environment is ready without provisioning infrastructure manually.
- Record the source commit and shared data version.

## Starting state

- You are signed in with the credentials provided by the event platform.
- Automated deployment has started.
- The Caldova feature request and source repository are available read-only.

## Task 1 - Review the request

1. Open the supplied feature request.
2. Review the expected clinical-trial panel, safety-signal panel, citations, and responsible-use wording.
3. Record the issue identifier and source commit in the lab worksheet.

## Task 2 - Check readiness

1. Run the supplied readiness check from the lab environment.
2. Confirm the result identifies the deployment as running, ready, or failed with a named resource.
3. If deployment is still running, continue reviewing the architecture until the check reports ready.

## Checkpoint

- The readiness check reports that the required resources are healthy.
- You have recorded the issue identifier, source commit, and data version.

## Troubleshooting

| Symptom | Check | Recovery |
|---|---|---|
| Deployment is still running | Confirm the current elapsed time | Continue the architecture review and retry at minute 5 |
| Readiness reports one failed resource | Record the resource and operation | Use the facilitator recovery path for that resource |
| Data version is missing | Check the deployment outputs | Use the prepared fallback manifest |

## Segment outcome

The environment, request, source version, and data version are ready for the hands-on work.
