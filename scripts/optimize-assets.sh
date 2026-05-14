#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

GHOSTSCRIPT_BIN="$(command -v gsc || command -v gs || true)"

if [[ -z "$GHOSTSCRIPT_BIN" ]]; then
  echo "Ghostscript is required to compress PDFs." >&2
  exit 1
fi

tmp_base() {
  mktemp "${TMPDIR:-/tmp}/deepagents-asset-XXXXXX"
}

update_path_references() {
  local from="$1" to="$2"
  local matched=0 file

  while IFS= read -r -d '' file; do
    matched=1
    perl -0pi -e "s/\Q$from\E/$to/g" "$file"
  done < <(grep -rlZ --binary-files=without-match --exclude-dir=.git --fixed-strings "$from" .)

  if (( matched )); then
    echo "Updated references: $from -> $to"
  fi
}

convert_jpeg_uploads_to_png() {
  local file target tmp out

  while IFS= read -r -d '' file; do
    target="${file%.*}.png"

    if [[ -e "$target" ]]; then
      echo "Cannot convert $file: target already exists at $target" >&2
      exit 1
    fi

    tmp="$(tmp_base)"
    rm -f "$tmp"
    out="$tmp.png"

    ffmpeg -y -loglevel error -i "$file" -frames:v 1 -pix_fmt pal8 -compression_level 100 "$out" </dev/null
    mv "$out" "$target"
    rm -f "$file"

    update_path_references "$file" "$target"
    echo "Converted $file -> $target"
  done < <(find public -type f \( -iname '*.jpg' -o -iname '*.jpeg' \) -print0)
}

normalize_png_assets() {
  local file mime tmp out

  while IFS= read -r -d '' file; do
    mime="$(file --brief --mime-type "$file")"

    if [[ "$mime" == "image/png" ]]; then
      continue
    fi

    if [[ "$mime" != "image/jpeg" ]]; then
      echo "Unsupported PNG payload: $file ($mime)" >&2
      exit 1
    fi

    tmp="$(tmp_base)"
    rm -f "$tmp"
    out="$tmp.png"

    ffmpeg -y -loglevel error -i "$file" -frames:v 1 -pix_fmt pal8 -compression_level 100 "$out" </dev/null
    mv "$out" "$file"

    echo "Normalized $file"
  done < <(find public -type f -name '*.png' -print0)
}

compress_pdfs() {
  local file tmp out old_size new_size

  while IFS= read -r -d '' file; do
    tmp="$(tmp_base)"
    rm -f "$tmp"
    out="$tmp.pdf"

    "$GHOSTSCRIPT_BIN" \
      -sDEVICE=pdfwrite \
      -dCompatibilityLevel=1.6 \
      -dPDFSETTINGS=/ebook \
      -dNOPAUSE \
      -dQUIET \
      -dBATCH \
      -dDetectDuplicateImages=true \
      -dCompressFonts=true \
      -dSubsetFonts=true \
      -sOutputFile="$out" \
      "$file" \
      </dev/null

    old_size="$(wc -c < "$file")"
    new_size="$(wc -c < "$out")"

    if (( new_size < old_size )); then
      mv "$out" "$file"
      echo "Compressed $file"
    else
      rm -f "$out"
    fi
  done < <(find public -type f -name '*.pdf' -print0)
}

convert_jpeg_uploads_to_png
normalize_png_assets
compress_pdfs
