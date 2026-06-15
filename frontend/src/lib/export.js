import * as XLSX from 'xlsx';
const FETCH_PAGE_SIZE = 500;
export async function fetchAllPaginated(fetcher, baseParams = {}) {
    const first = await fetcher({ ...baseParams, page: 1, page_size: FETCH_PAGE_SIZE });
    const rows = [...first.results];
    const total = first.count ?? rows.length;
    let page = 2;
    while (rows.length < total && first.next !== null) {
        const next = await fetcher({ ...baseParams, page, page_size: FETCH_PAGE_SIZE });
        rows.push(...next.results);
        if (next.next === null || next.results.length === 0)
            break;
        page += 1;
    }
    return rows;
}
function toCellValue(cell) {
    if (cell === null || cell === undefined)
        return '';
    return cell;
}
function csvEscape(value) {
    if (value === null || value === undefined)
        return '';
    const str = String(value);
    if (/[",\n\r]/.test(str)) {
        return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
}
function buildCsv(rows, columns) {
    const header = columns.map((c) => csvEscape(c.header)).join(',');
    const body = rows
        .map((row) => columns.map((c) => csvEscape(c.value(row))).join(','))
        .join('\n');
    return `${header}\n${body}`;
}
function buildJson(rows, columns) {
    const objects = rows.map((row) => columns.reduce((acc, c) => {
        acc[c.key] = c.value(row);
        return acc;
    }, {}));
    return JSON.stringify(objects, null, 2);
}
function buildXlsx(rows, columns, sheetName) {
    const aoa = [
        columns.map((c) => c.header),
        ...rows.map((row) => columns.map((c) => toCellValue(c.value(row)))),
    ];
    const worksheet = XLSX.utils.aoa_to_sheet(aoa);
    worksheet['!cols'] = columns.map((c) => ({
        wch: Math.max(c.header.length + 2, 12),
    }));
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, sheetName.slice(0, 31) || 'Sheet1');
    return XLSX.write(workbook, { type: 'array', bookType: 'xlsx' });
}
function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function timestamp() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return (`${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}` +
        `-${pad(d.getHours())}${pad(d.getMinutes())}`);
}
/** Excel tab names must be ≤31 chars, free of `[]:*?/\`, and unique within a workbook. */
function sanitizeSheetName(name, used) {
    const base = name.replace(/[\\/?*[\]:]/g, ' ').trim().slice(0, 31) || 'Sheet';
    let candidate = base;
    let n = 2;
    while (used.has(candidate.toLowerCase())) {
        const suffix = ` (${n})`;
        candidate = `${base.slice(0, 31 - suffix.length)}${suffix}`;
        n += 1;
    }
    used.add(candidate.toLowerCase());
    return candidate;
}
function sheetToAoa(sheet) {
    return [
        sheet.columns.map((c) => c.header),
        ...sheet.rows.map((row) => sheet.columns.map((c) => toCellValue(c.value(row)))),
    ];
}
/**
 * Bundle several tables into a single downloadable file:
 *  - xlsx → one worksheet per table
 *  - json → one object keyed by each table's `key`
 *  - csv  → one file with a labelled `# Section` block per table
 */
export function exportMultiSheet(sheets, format, filename) {
    const stamp = timestamp();
    if (format === 'json') {
        const payload = sheets.reduce((acc, s) => {
            acc[s.key] = s.rows.map((row) => s.columns.reduce((obj, c) => {
                obj[c.key] = c.value(row);
                return obj;
            }, {}));
            return acc;
        }, {});
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        triggerDownload(blob, `${filename}-${stamp}.json`);
        return;
    }
    if (format === 'csv') {
        const sections = sheets.map((s) => {
            const header = s.columns.map((c) => csvEscape(c.header)).join(',');
            const body = s.rows
                .map((row) => s.columns.map((c) => csvEscape(c.value(row))).join(','))
                .join('\n');
            const heading = csvEscape(`# ${s.label} (${s.rows.length})`);
            return `${heading}\n${body ? `${header}\n${body}` : header}`;
        });
        const csv = sections.join('\n\n\n');
        // Prepend UTF-8 BOM so Excel opens accented characters correctly.
        const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8;' });
        triggerDownload(blob, `${filename}-${stamp}.csv`);
        return;
    }
    const workbook = XLSX.utils.book_new();
    const used = new Set();
    for (const s of sheets) {
        const worksheet = XLSX.utils.aoa_to_sheet(sheetToAoa(s));
        worksheet['!cols'] = s.columns.map((c) => ({ wch: Math.max(c.header.length + 2, 12) }));
        XLSX.utils.book_append_sheet(workbook, worksheet, sanitizeSheetName(s.sheetName, used));
    }
    const buffer = XLSX.write(workbook, { type: 'array', bookType: 'xlsx' });
    const blob = new Blob([buffer], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    triggerDownload(blob, `${filename}-${stamp}.xlsx`);
}
export function exportRows(rows, columns, format, filename) {
    const stamp = timestamp();
    const sheetName = filename.replace(/[^a-z0-9_-]+/gi, '_').slice(0, 31) || 'data';
    if (format === 'csv') {
        const csv = buildCsv(rows, columns);
        // Prepend UTF-8 BOM so Excel opens accented characters correctly.
        const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8;' });
        triggerDownload(blob, `${filename}-${stamp}.csv`);
        return;
    }
    if (format === 'json') {
        const json = buildJson(rows, columns);
        const blob = new Blob([json], { type: 'application/json' });
        triggerDownload(blob, `${filename}-${stamp}.json`);
        return;
    }
    const buffer = buildXlsx(rows, columns, sheetName);
    const blob = new Blob([buffer], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    triggerDownload(blob, `${filename}-${stamp}.xlsx`);
}
