/**
 * Export a DOM element to a multi-page A4 PDF.
 * Uses html2canvas (screenshot of the element at its on-screen width, so the
 * layout looks exactly like the page) + jsPDF (slices it into A4 pages).
 */
export async function exportElementToPdf(el, filename) {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([import("html2canvas"), import("jspdf")]);
  const canvas = await html2canvas(el, {
    scale: 2,
    useCORS: true,
    backgroundColor: "#ffffff",
    windowWidth: Math.max(el.scrollWidth, 1400),
    ignoreElements: (node) => node.classList?.contains("no-pdf"),
  });
  const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const margin = 8;
  const pageW = pdf.internal.pageSize.getWidth() - margin * 2;
  const pageH = pdf.internal.pageSize.getHeight() - margin * 2;
  const pxPerPage = Math.floor((canvas.width * pageH) / pageW);

  for (let y = 0, page = 0; y < canvas.height; y += pxPerPage, page++) {
    const h = Math.min(pxPerPage, canvas.height - y);
    const slice = document.createElement("canvas");
    slice.width = canvas.width;
    slice.height = h;
    const ctx = slice.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, slice.width, slice.height);
    ctx.drawImage(canvas, 0, y, canvas.width, h, 0, 0, canvas.width, h);
    if (page > 0) pdf.addPage();
    pdf.addImage(slice.toDataURL("image/jpeg", 0.92), "JPEG", margin, margin, pageW, (h * pageW) / canvas.width);
  }
  pdf.save(filename);
}
