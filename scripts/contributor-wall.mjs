export function buildWall(contributors) {
  const markerStart = '<!-- contributors:start -->';
  const markerEnd = '<!-- contributors:end -->';

  if (contributors.length === 0) {
    return [
      markerStart,
      '_暂无贡献者数据，欢迎成为第一个贡献者。_',
      markerEnd,
    ].join('\n');
  }

  const cells = contributors.map((contributor) => [
    '<td align="center" valign="top" width="14.28%">',
    `  <a href="${contributor.profileUrl}">`,
    `    <img src="${contributor.avatarUrl}" width="72" height="72" alt="${contributor.login}" style="border-radius:50%;" /><br />`,
    `    <sub><strong>${contributor.login}</strong></sub>`,
    '  </a><br />',
    `  <sub>${contributor.contributions} commit${contributor.contributions === 1 ? '' : 's'}</sub>`,
    '</td>',
  ].join('\n'));

  const rows = [];
  for (let index = 0; index < cells.length; index += 7) {
    rows.push('<tr>');
    rows.push(cells.slice(index, index + 7).join('\n'));
    rows.push('</tr>');
  }

  return [
    markerStart,
    '<table>',
    ...rows,
    '</table>',
    markerEnd,
  ].join('\n');
}
