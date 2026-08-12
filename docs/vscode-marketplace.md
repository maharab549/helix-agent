# Publish Helix Agent to the VS Code Marketplace

This document is the release checklist for making Helix appear in VS Code extension search.

## One-Time Marketplace Setup

1. Create or choose a Visual Studio Marketplace publisher.
2. Make sure `integrations/vscode/package.json` uses that exact publisher ID in the `publisher` field.
3. Create a Marketplace personal access token with permission to publish extensions.
4. Add the token to this GitHub repo as an Actions secret named `VSCE_PAT`.

## Local Package Test

```powershell
cd integrations/vscode
npm install
npm run check
npx vsce package --no-dependencies
```

Install the generated `.vsix` locally:

```powershell
code --install-extension .\helix-agent-vscode-0.1.0.vsix
```

## Publish From GitHub

1. Push the repo.
2. Open GitHub Actions.
3. Run the `VS Code Extension` workflow manually.
4. Set `publish` to `true`.

The extension will become searchable in VS Code after the Marketplace listing finishes indexing.

## Publish Locally

```powershell
cd integrations/vscode
npx vsce login <publisher-id>
npx vsce publish --no-dependencies
```

## Before Every Release

- Update `integrations/vscode/package.json` version.
- Update `integrations/vscode/CHANGELOG.md`.
- Run Python tests from the repo root.
- Run `npm run check` and `npx vsce package --no-dependencies`.
