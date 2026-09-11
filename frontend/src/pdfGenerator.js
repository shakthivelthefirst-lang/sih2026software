import jsPDF from 'jspdf';
import 'jspdf-autotable';

// Helper for adding standard government header
function addGovernmentHeader(doc, title, subtitle) {
  doc.setFont("times", "bold");
  doc.setFontSize(16);
  doc.text("GOVERNMENT OF INDIA", 105, 20, { align: "center" });
  doc.setFontSize(14);
  doc.text("LAND RECORDS / LAND INFORMATION SYSTEM", 105, 28, { align: "center" });
  
  doc.line(14, 32, 196, 32);
  
  doc.setFontSize(12);
  doc.text(title, 105, 40, { align: "center" });
  if (subtitle) {
    doc.setFont("times", "normal");
    doc.setFontSize(10);
    doc.text(subtitle, 105, 46, { align: "center" });
  }
  
  doc.line(14, 50, 196, 50);
  return 55; // Next Y position
}

// Helper for adding a disclaimer at the bottom
function addDisclaimer(doc) {
  const pageHeight = doc.internal.pageSize.height;
  doc.setFont("times", "italic");
  doc.setFontSize(8);
  doc.setTextColor(100);
  const text = "DISCLAIMER: This is a system-generated document based on information currently available in the application. It is not an official Government of India land record, legal certificate, title document, or government-issued authentication unless issued or authenticated by the competent authority.";
  const lines = doc.splitTextToSize(text, 182);
  doc.text(lines, 14, pageHeight - 15);
  doc.setTextColor(0); // Reset
}

// Feature A: Generate OCR PDF
export function generateOCRPdf(documentId, ocrData, fields) {
  const doc = new jsPDF();
  
  const dateStr = new Date().toLocaleString();
  const subtitle = `Document Reference No.: ${documentId || "N/A"} | Date of Generation: ${dateStr}`;
  let y = addGovernmentHeader(doc, "OCR DOCUMENT EXTRACTION REPORT", subtitle);

  doc.setFont("times", "bold");
  doc.setFontSize(11);
  doc.text("DOCUMENT INFORMATION", 14, y);
  y += 6;
  doc.setFont("times", "normal");
  doc.setFontSize(10);
  doc.text(`OCR Status: ${ocrData.ocr_status || "N/A"}`, 14, y); y += 5;
  if (ocrData.ocr_confidence) {
    doc.text(`Confidence: ${Math.round(ocrData.ocr_confidence * 100)}%`, 14, y); y += 5;
  }
  y += 5;

  // Extracted fields
  if (fields && Object.keys(fields).length > 0) {
    doc.setFont("times", "bold");
    doc.setFontSize(11);
    doc.text("LAND RECORD INFORMATION", 14, y);
    y += 6;
    
    const tableData = [];
    for (const [key, val] of Object.entries(fields)) {
      tableData.push([key.replace(/_/g, " ").toUpperCase(), val || "-"]);
    }
    
    doc.autoTable({
      startY: y,
      head: [['Field', 'Extracted Value']],
      body: tableData,
      theme: 'grid',
      styles: { font: 'times', fontSize: 10 },
      headStyles: { fillColor: [240, 240, 240], textColor: [0, 0, 0], fontStyle: 'bold' }
    });
    
    y = doc.lastAutoTable.finalY + 10;
  }

  // Raw OCR Text if available (handling long text gracefully)
  if (ocrData.raw_text) {
    if (y > doc.internal.pageSize.height - 40) {
      doc.addPage();
      y = 20;
    }
    doc.setFont("times", "bold");
    doc.setFontSize(11);
    doc.text("OCR EXTRACTED CONTENT", 14, y);
    y += 6;
    
    doc.setFont("times", "normal");
    doc.setFontSize(10);
    const textLines = doc.splitTextToSize(ocrData.raw_text, 182);
    
    // Manual pagination for very long text
    for (let i = 0; i < textLines.length; i++) {
      if (y > doc.internal.pageSize.height - 25) {
        addDisclaimer(doc);
        doc.addPage();
        y = 20;
      }
      doc.text(textLines[i], 14, y);
      y += 5;
    }
  }

  addDisclaimer(doc);

  // Add page numbers
  const pageCount = doc.internal.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFont("times", "normal");
    doc.setFontSize(8);
    doc.text(`Page ${i} of ${pageCount}`, doc.internal.pageSize.width / 2, doc.internal.pageSize.height - 5, { align: 'center' });
  }

  const safeId = (documentId || "Unknown").toString().replace(/[^a-z0-9]/gi, '_');
  const dStr = new Date().toISOString().slice(0, 10);
  doc.save(`OCR_Land_Document_${safeId}_${dStr}.pdf`);
}

// Feature B: Generate Current Land Parcel Report
export function generateLandParcelReport(parcel) {
  const doc = new jsPDF();
  const dateStr = new Date().toLocaleString();
  const reportRef = `RPT-${Math.floor(Math.random() * 1000000).toString().padStart(6, '0')}`;
  
  const subtitle = `Report Reference No.: ${reportRef} | Date: ${dateStr}`;
  let y = addGovernmentHeader(doc, "CURRENT LAND PARCEL STATUS REPORT", subtitle);

  doc.setFont("times", "bold");
  doc.setFontSize(11);
  doc.text("1. LAND PARCEL IDENTIFICATION", 14, y); y += 6;
  doc.setFont("times", "normal");
  doc.setFontSize(10);
  doc.text(`Land Parcel ID: ${parcel.id || "N/A"}`, 14, y); y += 5;
  doc.text(`Record ID: ${parcel.record_id || "N/A"}`, 14, y); y += 5;
  doc.text(`Survey Number: ${parcel.survey_no || "N/A"}`, 14, y); y += 5;
  doc.text(`Sub-Division Number: ${parcel.subdivision || "N/A"}`, 14, y); y += 5;
  doc.text(`Project Reference: ${parcel.project_id || "N/A"}`, 14, y); y += 10;

  doc.setFont("times", "bold");
  doc.setFontSize(11);
  doc.text("2. LOCATION DETAILS", 14, y); y += 6;
  doc.setFont("times", "normal");
  doc.setFontSize(10);
  doc.text(`State: ${parcel.state || "Not available in system records"}`, 14, y); y += 5;
  doc.text(`District: ${parcel.district || "N/A"}`, 14, y); y += 5;
  doc.text(`Taluk: ${parcel.taluk || "N/A"}`, 14, y); y += 5;
  doc.text(`Village: ${parcel.village || "N/A"}`, 14, y); y += 10;

  doc.setFont("times", "bold");
  doc.setFontSize(11);
  doc.text("3. LAND DETAILS", 14, y); y += 6;
  doc.setFont("times", "normal");
  doc.setFontSize(10);
  doc.text(`Land Area: ${parcel.area || "N/A"} ${parcel.area ? "Acres" : ""}`, 14, y); y += 5;
  doc.text(`Classification: ${parcel.classification || "N/A"}`, 14, y); y += 10;
  
  doc.setFont("times", "bold");
  doc.setFontSize(11);
  doc.text("4. CURRENT STATUS & RISK", 14, y); y += 6;
  doc.setFont("times", "normal");
  doc.setFontSize(10);
  doc.text(`Acquisition Status: ${parcel.acquisition_status || "N/A"}`, 14, y); y += 5;
  doc.text(`Risk Category: ${parcel.risk_category || "N/A"}`, 14, y); y += 5;
  doc.text(`Risk Score: ${parcel.risk_score ?? "N/A"}`, 14, y); y += 10;
  
  if (parcel.assignment_status) {
    doc.text(`Field Assignment Status: ${parcel.assignment_status}`, 14, y); y += 5;
  }
  
  doc.setFont("times", "bold");
  doc.setFontSize(11);
  doc.text("5. SYSTEM INFORMATION", 14, y); y += 6;
  doc.setFont("times", "normal");
  doc.setFontSize(10);
  doc.text(`Application Name: LANDNEXUS`, 14, y); y += 5;
  doc.text(`Generation Timestamp: ${dateStr}`, 14, y); y += 10;

  addDisclaimer(doc);

  // Add page numbers
  const pageCount = doc.internal.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFont("times", "normal");
    doc.setFontSize(8);
    doc.text(`Page ${i} of ${pageCount}`, doc.internal.pageSize.width / 2, doc.internal.pageSize.height - 5, { align: 'center' });
  }

  const safeId = (parcel.id || parcel.survey_no || "Unknown").toString().replace(/[^a-z0-9]/gi, '_');
  const dStr = new Date().toISOString().slice(0, 10);
  doc.save(`Land_Parcel_Current_Report_${safeId}_${dStr}.pdf`);
}
