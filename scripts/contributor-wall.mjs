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

  const cells = contributors.map((contributor) => {
    const displayedLogin = contributor.login.length > 7
      ? `${contributor.login.slice(0, 7)}…`
      : contributor.login;
    const padding = 8 - displayedLogin.length;
    const paddedLogin = [
      '&#160;'.repeat(Math.floor(padding / 2)),
      displayedLogin.replaceAll('-', '&#8209;'),
      '&#160;'.repeat(Math.ceil(padding / 2)),
    ].join('');

    return [
      '<td align="center" valign="top" width="12.5%">',
      `  <a href="${contributor.profileUrl}" title="${contributor.login}">`,
      `    <img src="${contributor.avatarUrl}" width="72" height="72" alt="${contributor.login}" style="border-radius:50%;" /><br />`,
      `    <sub><samp>${paddedLogin}</samp></sub>`,
      '  </a><br />',
      `  <sub>${contributor.contributions} commit${contributor.contributions === 1 ? '' : 's'}</sub>`,
      '</td>',
    ].join('\n');
  });

  const rows = [];
  for (let index = 0; index < cells.length; index += 8) {
    rows.push('<tr>');
    rows.push(cells.slice(index, index + 8).join('\n'));
    rows.push('</tr>');
  }

  return [
    markerStart,
    '<table width="100%">',
    ...rows,
    '</table>',
    markerEnd,
  ].join('\n');
}
