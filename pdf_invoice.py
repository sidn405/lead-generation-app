# pdf_invoice.py - PDF invoice generator for proof of delivery

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import os
from postgres_credit_system import credit_system

def generate_invoice_pdf(username: str, transaction_id: str, output_dir: str = "invoices") -> str:
    """Generate PDF invoice for credit purchase"""
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Get invoice data
    invoice_data = credit_system.generate_invoice_data(username, transaction_id)
    
    if not invoice_data:
        return None
    
    # Create filename
    filename = f"invoice_{invoice_data['invoice_number']}_{username}.pdf"
    filepath = os.path.join(output_dir, filename)
    
    # Create PDF document
    doc = SimpleDocTemplate(filepath, pagesize=letter, topMargin=1*inch)
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.darkblue,
        alignment=1  # Center alignment
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    # Build PDF content
    content = []
    
    # Header
    content.append(Paragraph("LEAD GENERATOR EMPIRE", title_style))
    content.append(Paragraph("Digital Credits Invoice", styles['Heading2']))
    content.append(Spacer(1, 20))
    
    # Invoice details
    invoice_info = [
        ["Invoice Number:", invoice_data['invoice_number']],
        ["Date:", datetime.fromisoformat(invoice_data['date']).strftime("%B %d, %Y")],
        ["Customer:", invoice_data['customer']['username']],
        ["Email:", invoice_data['customer']['email']],
        ["Payment Method:", invoice_data['payment_method']]
    ]
    
    invoice_table = Table(invoice_info, colWidths=[2*inch, 3*inch])
    invoice_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    content.append(invoice_table)
    content.append(Spacer(1, 30))
    
    # Items table
    content.append(Paragraph("Items Purchased", heading_style))
    
    items_data = [
        ["Description", "Credits", "Amount"],
    ]
    
    for item in invoice_data['items']:
        items_data.append([
            item['description'],
            f"{item['credits']} credits",
            f"${item['amount']:.2f}"
        ])
    
    # Add total row
    items_data.append(["", "TOTAL:", f"${invoice_data['total']:.2f}"])
    
    items_table = Table(items_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        
        # Data rows
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        
        # Total row
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        
        # Borders
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        
        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    content.append(items_table)
    content.append(Spacer(1, 30))
    
    # Terms and conditions
    content.append(Paragraph("Terms & Conditions", heading_style))
    
    terms_text = """
    <b>DIGITAL PRODUCT - NO REFUNDS</><br/><br/>
    
    • This invoice serves as proof of purchase for digital credits<br/>
    • Credits are delivered instantly upon payment confirmation<br/>
    • NO REFUNDS: All sales are final due to digital nature of product<br/>
    • Credits expire 90 days from purchase date<br/>
    • Credits are for legitimate business lead generation only<br/>
    • Abuse of service may result in account termination<br/>
    • By purchasing, customer agrees to our Terms of Service<br/><br/>
    
    <b>Support:</b> For technical issues (not refund requests), contact support@leadgeneratorempire.com
    """
    
    content.append(Paragraph(terms_text, styles['Normal']))
    content.append(Spacer(1, 20))
    
    # Footer
    footer_text = """
    <b>Lead Generator Empire</b><br/>
    Digital Marketing Solutions<br/>
    This invoice serves as proof of delivery for digital credits.<br/>
    Generated automatically - no signature required.
    """
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=1  # Center
    )
    
    content.append(Paragraph(footer_text, footer_style))
    
    # Build PDF
    doc.build(content)
    
    return filepath

def generate_delivery_confirmation_pdf(username: str, leads_data: list, platform: str, output_dir: str = "delivery_confirmations") -> str:
    """Generate delivery confirmation PDF showing leads were provided"""
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Create filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"delivery_{username}_{platform}_{timestamp}.pdf"
    filepath = os.path.join(output_dir, filename)
    
    # Create PDF
    doc = SimpleDocTemplate(filepath, pagesize=letter, topMargin=1*inch)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=20,
        textColor=colors.darkblue,
        alignment=1
    )
    
    content = []
    
    # Header
    content.append(Paragraph("DELIVERY CONFIRMATION", title_style))
    content.append(Paragraph("Lead Generator Empire", styles['Heading2']))
    content.append(Spacer(1, 20))
    
    # Delivery details
    delivery_info = [
        ["Customer:", username],
        ["Platform:", platform.title()],
        ["Delivery Date:", datetime.now().strftime("%B %d, %Y at %H:%M UTC")],
        ["Total Leads Delivered:", str(len(leads_data))],
        ["Credits Consumed:", str(len(leads_data))],
        ["Delivery Method:", "Digital Download (CSV)"]
    ]
    
    delivery_table = Table(delivery_info, colWidths=[2*inch, 3*inch])
    delivery_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    content.append(delivery_table)
    content.append(Spacer(1, 30))
    
    # Sample of delivered data (first 5 leads)
    content.append(Paragraph("Sample of Delivered Leads:", styles['Heading3']))
    
    sample_data = [["Name", "Platform", "Bio Preview"]]
    
    for i, lead in enumerate(leads_data[:5]):
        name = lead.get('name', 'N/A')
        bio = lead.get('bio', 'N/A')
        bio_preview = bio[:50] + "..." if len(bio) > 50 else bio
        
        sample_data.append([name, platform.title(), bio_preview])
    
    if len(leads_data) > 5:
        sample_data.append([f"... and {len(leads_data) - 5} more leads", "", ""])
    
    sample_table = Table(sample_data, colWidths=[2*inch, 1*inch, 3*inch])
    sample_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        
        # Data
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    content.append(sample_table)
    content.append(Spacer(1, 20))
    
    # Confirmation statement
    confirmation_text = f"""
    <b>DELIVERY CONFIRMED</b><br/><br/>
    
    This document confirms that {len(leads_data)} leads were successfully delivered to customer "{username}" 
    on {datetime.now().strftime("%B %d, %Y at %H:%M UTC")} from the {platform.title()} platform.<br/><br/>
    
    <b>What was delivered:</b><br/>
    • {len(leads_data)} complete lead profiles<br/>
    • Contact information (names, handles, bios)<br/>
    • Platform-specific data<br/>
    • CSV format for easy import<br/><br/>
    
    <b>Credits:</b> {len(leads_data)} credits were consumed from customer's account.<br/><br/>
    
    This serves as proof of delivery for digital products. No refunds available for delivered digital goods.
    """
    
    content.append(Paragraph(confirmation_text, styles['Normal']))
    
    # Build PDF
    doc.build(content)
    
    return filepath

# Streamlit integration functions
def download_invoice_button(username: str, transaction_id: str):
    """Create download button for invoice PDF"""
    import streamlit as st
    
    if st.button("📄 Download Invoice PDF", use_container_width=True):
        try:
            pdf_path = generate_invoice_pdf(username, transaction_id)
            
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as pdf_file:
                    st.download_button(
                        label="💾 Save Invoice PDF",
                        data=pdf_file.read(),
                        file_name=f"invoice_{username}_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                st.success("✅ Invoice PDF generated successfully!")
            else:
                st.error("❌ Error generating invoice PDF")
                
        except Exception as e:
            st.error(f"❌ PDF generation error: {str(e)}")

def download_delivery_confirmation_button(username: str, leads_data: list, platform: str):
    """Create download button for delivery confirmation PDF"""
    import streamlit as st
    
    if st.button(f"📋 Download Delivery Confirmation", use_container_width=True):
        try:
            pdf_path = generate_delivery_confirmation_pdf(username, leads_data, platform)
            
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as pdf_file:
                    st.download_button(
                        label="💾 Save Delivery Confirmation",
                        data=pdf_file.read(),
                        file_name=f"delivery_{platform}_{username}_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                st.success("✅ Delivery confirmation generated!")
            else:
                st.error("❌ Error generating delivery confirmation")
                
        except Exception as e:
            st.error(f"❌ PDF generation error: {str(e)}")