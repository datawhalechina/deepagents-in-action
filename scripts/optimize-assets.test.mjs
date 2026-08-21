import assert from "node:assert/strict";
import { chmod, copyFile, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import test from "node:test";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("PDF optimization keeps slide text readable", async () => {
  const fixtureRoot = await mkdtemp(path.join(tmpdir(), "deepagents-pdf-quality-"));

  try {
    const scriptsDir = path.join(fixtureRoot, "scripts");
    const publicDir = path.join(fixtureRoot, "public");
    const binDir = path.join(fixtureRoot, "bin");
    const argsFile = path.join(fixtureRoot, "ghostscript-args.txt");
    const pdfPath = path.join(publicDir, "test.pdf");
    const fakeGhostscript = path.join(binDir, "gsc");

    await Promise.all([
      mkdir(scriptsDir, { recursive: true }),
      mkdir(publicDir, { recursive: true }),
      mkdir(binDir, { recursive: true }),
    ]);
    await copyFile(
      path.join(repoRoot, "scripts", "optimize-assets.sh"),
      path.join(scriptsDir, "optimize-assets.sh"),
    );
    await writeFile(pdfPath, Buffer.alloc(4096, 1));
    await writeFile(
      fakeGhostscript,
      `#!/bin/sh
printf '%s\\n' "$@" > "$GS_ARGS_FILE"
output=''
input=''
for argument in "$@"; do
  case "$argument" in
    -sOutputFile=*) output="\${argument#-sOutputFile=}" ;;
    -*) ;;
    *) input="$argument" ;;
  esac
done
cp "$input" "$output"
`,
    );
    await chmod(fakeGhostscript, 0o755);

    const result = spawnSync("bash", ["scripts/optimize-assets.sh", "public/test.pdf"], {
      cwd: fixtureRoot,
      encoding: "utf8",
      env: {
        ...process.env,
        GS_ARGS_FILE: argsFile,
        PATH: `${binDir}:${process.env.PATH ?? ""}`,
      },
    });

    assert.equal(result.status, 0, result.stderr || result.stdout);
    const args = (await readFile(argsFile, "utf8")).split("\n");

    assert.ok(args.includes("-dPDFSETTINGS=/ebook"));
    assert.ok(args.includes("-dPassThroughJPEGImages=true"));
    assert.ok(args.includes("-dColorImageResolution=150"));
    assert.ok(args.includes("-dGrayImageResolution=150"));
    assert.ok(args.includes("-dMonoImageResolution=300"));
    assert.ok(args.includes("-dJPEGQ=90"));
  } finally {
    await rm(fixtureRoot, { recursive: true, force: true });
  }
});

test("PDF optimization ignores negligible savings from a repeated pass", async () => {
  const fixtureRoot = await mkdtemp(path.join(tmpdir(), "deepagents-pdf-idempotence-"));

  try {
    const scriptsDir = path.join(fixtureRoot, "scripts");
    const publicDir = path.join(fixtureRoot, "public");
    const binDir = path.join(fixtureRoot, "bin");
    const pdfPath = path.join(publicDir, "test.pdf");
    const fakeGhostscript = path.join(binDir, "gsc");

    await Promise.all([
      mkdir(scriptsDir, { recursive: true }),
      mkdir(publicDir, { recursive: true }),
      mkdir(binDir, { recursive: true }),
    ]);
    await copyFile(
      path.join(repoRoot, "scripts", "optimize-assets.sh"),
      path.join(scriptsDir, "optimize-assets.sh"),
    );
    await writeFile(pdfPath, Buffer.alloc(8192, 1));
    await writeFile(
      fakeGhostscript,
      `#!/bin/sh
output=''
input=''
for argument in "$@"; do
  case "$argument" in
    -sOutputFile=*) output="\${argument#-sOutputFile=}" ;;
    -*) ;;
    *) input="$argument" ;;
  esac
done
dd if="$input" of="$output" bs=1 count=8191 2>/dev/null
`,
    );
    await chmod(fakeGhostscript, 0o755);

    const result = spawnSync("bash", ["scripts/optimize-assets.sh", "public/test.pdf"], {
      cwd: fixtureRoot,
      encoding: "utf8",
      env: {
        ...process.env,
        PATH: `${binDir}:${process.env.PATH ?? ""}`,
      },
    });

    assert.equal(result.status, 0, result.stderr || result.stdout);
    assert.equal((await readFile(pdfPath)).length, 8192);
  } finally {
    await rm(fixtureRoot, { recursive: true, force: true });
  }
});
