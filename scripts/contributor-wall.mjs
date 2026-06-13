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

  const formatLogin = (login) => {
    const displayedLogin = login.length > 10 ? `${login.slice(0, 10)}…` : login;
    const padding = 11 - displayedLogin.length;
    const leftPadding = '&#160;'.repeat(Math.floor(padding / 2));
    const rightPadding = '&#160;'.repeat(Math.ceil(padding / 2));

    return `${leftPadding}${displayedLogin}${rightPadding}`;
  };

  const cells = contributors.map((contributor) => [
    '<td align="center" valign="top" width="12.5%">',
    `  <a href="${contributor.profileUrl}" title="${contributor.login}">`,
    `    <img src="${contributor.avatarUrl}" width="72" height="72" alt="${contributor.login}" style="border-radius:50%;" /><br />`,
    `    <sub><samp>${formatLogin(contributor.login)}</samp></sub>`,
    '  </a><br />',
    `  <sub>${contributor.contributions} commit${contributor.contributions === 1 ? '' : 's'}</sub>`,
    '</td>',
  ].join('\n'));

  const rows = [];
  for (let index = 0; index < cells.length; index += 8) {
    rows.push('<tr>');
    rows.push(cells.slice(index, index + 8).join('\n'));
    rows.push('</tr>');
  }

  return [
    markerStart,
    '<table align="center" width="100%">',
    ...rows,
    '</table>',
    markerEnd,
  ].join('\n');
}
