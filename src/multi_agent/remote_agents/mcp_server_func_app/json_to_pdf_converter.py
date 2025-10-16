"""
JSON to PDF Report Converter
Converts reimbursement JSON data into a user-friendly PDF report with images.
"""

import json
import requests
from datetime import datetime
from io import BytesIO
from PIL import Image
import logging
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from dotenv import load_dotenv
from blob_utils import get_blob_client, get_sas_token  # Import from local blob_utils
import tempfile
import os
import sys
import fitz  # PyMuPDF for PDF processing

load_dotenv()

# Add the parent directory to sys.path if utils.py is in a different directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # Add current directory to sys.path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class ReimbursementPDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
        
    def setup_custom_styles(self):
        """Setup custom styles for the PDF report."""
        # Title style
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2E4057')
        )
        
        # Header style
        self.header_style = ParagraphStyle(
            'CustomHeader',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            textColor=colors.HexColor('#4A90A4')
        )
        
        # Summary style
        self.summary_style = ParagraphStyle(
            'CustomSummary',
            parent=self.styles['Normal'],
            fontSize=14,
            spaceAfter=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2E4057'),
            backColor=colors.HexColor('#F0F8FF')
        )
        
        # Normal text style
        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=10
        )

    def download_image_from_blob(self, blob_url: str) -> BytesIO:
        """
        Download image from Azure Blob Storage URL.
        
        Args:
            blob_url (str): The blob URL to download from
            
        Returns:
            BytesIO: Image data in memory
        """
        try:
            logger.info(f"Attempting to download image from: {blob_url}")
            
            # Try to download directly first (for public URLs or SAS URLs)
            response = requests.get(blob_url, timeout=30)
            if response.status_code == 200:
                content_size = len(response.content)
                logger.info(f"Successfully downloaded {content_size} bytes via direct URL")
                return BytesIO(response.content)
            
            # If direct download fails, try with blob client authentication
            logger.warning(f"Direct download failed with status {response.status_code}, trying with authentication")
            
            # Parse the URL to get container and blob name
            url_parts = blob_url.replace('https://', '').split('/')
            if len(url_parts) < 3:
                raise ValueError(f"Invalid blob URL format: {blob_url}")
                
            container_name = url_parts[1]
            blob_name = '/'.join(url_parts[2:]).split('?')[0]  # Remove SAS token if present
            
            logger.info(f"Attempting authenticated download - Container: {container_name}, Blob: {blob_name}")
            
            blob_client = get_blob_client()
            blob_client_instance = blob_client.get_blob_client(container=container_name, blob=blob_name)
            
            # Download blob data
            blob_data = blob_client_instance.download_blob().readall()
            logger.info(f"Successfully downloaded {len(blob_data)} bytes via authenticated client")
            return BytesIO(blob_data)
            
        except Exception as e:
            logger.error(f"Failed to download image from {blob_url}: {e}")
            print(f"Image download error: {e}")  # Additional logging for Azure Functions
            return None

    def is_pdf_content(self, data: BytesIO) -> bool:
        """
        Check if the data is a PDF file.
        
        Args:
            data (BytesIO): Data to check
            
        Returns:
            bool: True if data is PDF, False otherwise
        """
        try:
            # Read first few bytes to check PDF signature
            current_pos = data.tell()
            data.seek(0)
            header = data.read(4)
            data.seek(current_pos)
            
            return header == b'%PDF'
        except:
            return False

    def convert_pdf_first_page_to_image(self, pdf_data: BytesIO) -> BytesIO:
        """
        Convert the first page of a PDF to an image.
        
        Args:
            pdf_data (BytesIO): PDF data
            
        Returns:
            BytesIO: Image data of the first page
        """
        try:
            # Open PDF with PyMuPDF
            pdf_document = fitz.open(stream=pdf_data.getvalue(), filetype="pdf")
            print(f"PDF opened successfully, {len(pdf_document)} pages")
            
            # Get the first page
            first_page = pdf_document[0]
            page_rect = first_page.rect
            print(f"First page dimensions: {page_rect.width} x {page_rect.height}")
            
            # Convert page to image with higher resolution and different color space
            mat = fitz.Matrix(3.0, 3.0)  # Increased from 2x to 3x zoom for better quality
            
            # Try different rendering options for better results
            pix = first_page.get_pixmap(matrix=mat, alpha=False, colorspace=fitz.csRGB)
            print(f"Pixmap created: {pix.width} x {pix.height}")
            
            # Check if the pixmap is empty (all white)
            samples = pix.samples
            if len(set(samples[:300])) <= 2:  # Check first 300 bytes for variety
                print("Warning: PDF appears to be blank or very light content")
                # Try with different rendering settings
                pix = first_page.get_pixmap(matrix=mat, alpha=False, colorspace=fitz.csRGB, clip=page_rect)
            
            # Convert to PIL Image - use different format for better compatibility
            if pix.n == 4:  # RGBA
                img_data = pix.tobytes("png")
                pil_image = Image.open(BytesIO(img_data))
            else:  # RGB
                img_data = pix.tobytes("ppm")
                pil_image = Image.open(BytesIO(img_data))
            
            print(f"PIL image created: {pil_image.size}, mode: {pil_image.mode}")
            
            # Convert to JPEG and return as BytesIO
            img_bytes = BytesIO()
            pil_image.save(img_bytes, format='JPEG', quality=95)  # Increased quality from 85 to 95
            img_bytes.seek(0)
            print(f"JPEG conversion complete, size: {len(img_bytes.getvalue())} bytes")
            
            pdf_document.close()
            return img_bytes
            
        except Exception as e:
            logger.error(f"Failed to convert PDF to image: {e}")
            return None

    def process_image_for_pdf(self, image_data: BytesIO, max_width: float = 6*inch, max_height: float = 8*inch):
        """
        Process image data for inclusion in PDF. Handles both images and PDFs.
        
        Args:
            image_data (BytesIO): Image or PDF data
            max_width (float): Maximum width for the image
            max_height (float): Maximum height for the image
            
        Returns:
            RLImage: Processed image for ReportLab
        """
        try:
            # Check if the data is a PDF
            if self.is_pdf_content(image_data):
                logger.info("Processing PDF file - converting first page to image")
                print("Processing PDF file - converting first page to image")
                image_data = self.convert_pdf_first_page_to_image(image_data)
                if not image_data:
                    return None
            
            # Open image with PIL
            pil_image = Image.open(image_data)
            
            # Convert to RGB if necessary
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Calculate aspect ratio and resize
            aspect_ratio = pil_image.width / pil_image.height
            
            if aspect_ratio > max_width / max_height:
                # Width is the limiting factor
                new_width = max_width
                new_height = max_width / aspect_ratio
            else:
                # Height is the limiting factor
                new_height = max_height
                new_width = max_height * aspect_ratio
            
            # Resize image
            pil_image = pil_image.resize((int(new_width * 72 / inch), int(new_height * 72 / inch)), Image.Resampling.LANCZOS)
            
            # Use in-memory operations instead of temp files for Azure Functions compatibility
            try:
                # Save PIL image to BytesIO buffer as PNG
                img_buffer = BytesIO()
                pil_image.save(img_buffer, format='PNG', optimize=True)
                img_buffer.seek(0)  # Reset buffer position to beginning
                
                # Debug: Check buffer size
                buffer_size = len(img_buffer.getvalue())
                print(f"Created image buffer: size: {buffer_size} bytes, dimensions: {new_width:.1f}x{new_height:.1f}")
                
                # Create ReportLab image from BytesIO buffer
                rl_image = RLImage(img_buffer, width=new_width, height=new_height)
                
                # Store buffer reference to prevent garbage collection
                rl_image._img_buffer = img_buffer
                
                return rl_image
                
            except Exception as save_error:
                logger.error(f"Failed to create image buffer: {save_error}")
                raise save_error
            
        except Exception as e:
            logger.error(f"Failed to process image/PDF: {e}")
            print(f"Failed to process image/PDF: {e}")
            return None

    def create_details_table(self, details: list) -> Table:
        """
        Create a formatted table for reimbursement details.
        
        Args:
            details (list): List of reimbursement detail dictionaries
            
        Returns:
            Table: Formatted table for the PDF
        """
        # Table headers
        headers = ['Date', 'Category', 'Description', 'Claimed', 'Approved', 'Status']
        
        # Prepare table data
        table_data = [headers]
        
        for item in details:
            row = [
                item.get('Date', 'N/A'),
                item.get('Category', 'N/A'),
                self.truncate_text(item.get('Description', 'N/A'), 40),
                f"${item.get('Claimed Amount', 0):,.2f}",
                f"${item.get('Approved Amount', 0):,.2f}",
                item.get('Comment', 'N/A')
            ]
            table_data.append(row)
        
        # Create table
        table = Table(table_data, colWidths=[1*inch, 1.2*inch, 2.5*inch, 0.8*inch, 0.8*inch, 1*inch])
        
        # Apply table style
        table.setStyle(TableStyle([
            # Header row styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90A4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Data rows styling
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (3, 1), (4, -1), 'RIGHT'),  # Right align amount columns
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
        ]))
        
        return table

    def truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text if it's too long."""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."

    def generate_pdf_report(self, json_data: dict, output_path: str):
        """
        Generate a PDF report from JSON data.
        
        Args:
            json_data (dict): The reimbursement data
            output_path (str): Path where to save the PDF
        """
        try:
            # Create PDF document with smaller margins for more space
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=36,   # Reduced from 72
                leftMargin=36,    # Reduced from 72
                topMargin=36,     # Reduced from 72
                bottomMargin=36   # Increased from 18
            )

            sas_token = get_sas_token(os.environ.get("BLOB_CONTAINER_NAME", "images"))

            print("SAS Token:", sas_token)  # Debugging line to check SAS token            
            # Story elements
            story = []
            
            # Title
            title = Paragraph("Reimbursement Report", self.title_style)
            story.append(title)
            story.append(Spacer(1, 20))
            
            # Generated date
            date_text = f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"
            date_para = Paragraph(date_text, self.normal_style)
            story.append(date_para)
            story.append(Spacer(1, 20))
            
            # Summary section
            summary_header = Paragraph("Executive Summary", self.header_style)
            story.append(summary_header)
            
            summary_text = json_data.get('Summary', 'No summary available')
            summary_para = Paragraph(summary_text, self.summary_style)
            story.append(summary_para)
            story.append(Spacer(1, 30))
            
            # Details section
            details_header = Paragraph("Detailed Breakdown", self.header_style)
            story.append(details_header)
            
            # Details table
            details = json_data.get('Details', [])
            if details:
                details_table = self.create_details_table(details)
                story.append(details_table)
                story.append(Spacer(1, 30))
                
                # Add individual item details with images
                story.append(Paragraph("Supporting Documents", self.header_style))
                story.append(Spacer(1, 20))
                
                for i, item in enumerate(details, 1):
                    # Item header
                    item_title = f"Item {i}: {item.get('Category', 'Unknown Category')}"
                    item_para = Paragraph(item_title, ParagraphStyle(
                        'ItemTitle',
                        parent=self.styles['Heading2'],
                        fontSize=14,
                        spaceAfter=10,
                        textColor=colors.HexColor('#2E4057')
                    ))
                    story.append(item_para)
                    
                    # Item details
                    item_details = f"""
                    <b>Date:</b> {item.get('Date', 'N/A')}<br/>
                    <b>Description:</b> {item.get('Description', 'N/A')}<br/>
                    <b>Claimed Amount:</b> ${item.get('Claimed Amount', 0):,.2f}<br/>
                    <b>Approved Amount:</b> ${item.get('Approved Amount', 0):,.2f}<br/>
                    <b>Status:</b> {item.get('Comment', 'N/A')}
                    """
                    item_details_para = Paragraph(item_details, self.normal_style)
                    story.append(item_details_para)
                    story.append(Spacer(1, 20))  # Increased spacing
                    
                    # Download and add invoice image
                    invoice_link = item.get('invoice_link')
                    if invoice_link:
                        logger.info(f"Processing invoice document for item {i}: {invoice_link}")
                        sas_url = f"{invoice_link}?{sas_token}"
                        image_data = self.download_image_from_blob(sas_url)

                        if image_data:
                            # Check if it's a PDF or image
                            is_pdf = self.is_pdf_content(image_data)
                            doc_type = "PDF document" if is_pdf else "image"
                            logger.info(f"Document type detected: {doc_type}")
                            print(f"Document type detected: {doc_type}")
                            
                            processed_image = self.process_image_for_pdf(image_data)
                            if processed_image:
                                caption_text = f"Invoice Document ({doc_type}):"
                                if is_pdf:
                                    caption_text += " (First page shown)"
                                
                                story.append(Paragraph(caption_text, ParagraphStyle(
                                    'ImageCaption',
                                    parent=self.styles['Normal'],
                                    fontSize=12,  # Increased font size
                                    textColor=colors.HexColor('#666666'),
                                    spaceAfter=10
                                )))
                                story.append(processed_image)
                                # No temp file tracking needed - using in-memory buffers
                            else:
                                story.append(Paragraph(f"Invoice {doc_type} could not be processed.", self.normal_style))
                        else:
                            story.append(Paragraph("Invoice document could not be downloaded.", self.normal_style))
                    else:
                        story.append(Paragraph("No invoice document available.", self.normal_style))
                    
                    # Always add page break after each item for better readability
                    if i < len(details):
                        story.append(PageBreak())
            
            else:
                no_details_para = Paragraph("No detailed information available.", self.normal_style)
                story.append(no_details_para)
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"PDF report generated successfully: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate PDF report: {e}")
            raise

def upload_pdf_to_blob(pdf_path: str, container_name: str, blob_prefix: str, filename: str) -> str:
    """
    Upload PDF file to Azure Blob Storage and return a SAS URL for download.
    
    Args:
        pdf_path (str): Local path to the PDF file
        container_name (str): Azure blob container name
        blob_prefix (str): Prefix path within the container
        filename (str): Name for the uploaded file
        
    Returns:
        str: SAS URL of the uploaded blob (accessible for download)
    """
    try:
        from azure.storage.blob import BlobServiceClient, ContentSettings
        from blob_utils import get_blob_client
        
        # Get blob service client
        blob_service_client = get_blob_client()
        
        # Construct blob name with prefix
        blob_name = f"{blob_prefix}{filename}" if blob_prefix else filename
        
        # Get blob client
        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )
        
        # Ensure container exists
        try:
            container_client = blob_service_client.get_container_client(container_name)
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"Created container: {container_name}")
        except Exception as container_error:
            logger.warning(f"Container check/creation failed: {container_error}")
        
        # Read and upload PDF file
        with open(pdf_path, 'rb') as pdf_file:
            blob_client.upload_blob(
                pdf_file,
                overwrite=True,
                content_settings=ContentSettings(content_type='application/pdf')
            )
        
        logger.info(f"PDF uploaded successfully to: {blob_client.url}")
        
        # Generate SAS URL for download (valid for 7 days)

        sas_token = get_sas_token(container_name)
        
        # Create the full SAS URL
        sas_url = f"{blob_client.url}?{sas_token}"
        logger.info(f"Generated SAS URL for PDF download (valid for 7 days)")
        return sas_url
        
    except Exception as e:
        logger.error(f"Failed to upload PDF to blob storage: {e}")
        raise

def parse_blob_url_info(blob_url: str) -> tuple:
    """
    Parse Azure blob URL to extract container name and blob path prefix.
    
    Args:
        blob_url (str): Azure blob URL
        
    Returns:
        tuple: (container_name, blob_prefix) where blob_prefix is the directory path
    """
    try:
        # Remove protocol and split URL
        url_parts = blob_url.replace('https://', '').split('/')
        # url_parts[0] = storage_account.blob.core.windows.net
        # url_parts[1] = container_name
        # url_parts[2:] = blob path
        
        if len(url_parts) < 3:
            return "images", ""  # Default fallback
        
        container_name = url_parts[1]
        blob_path = '/'.join(url_parts[2:]).split('?')[0]  # Remove SAS token if present
        
        # Extract directory prefix (everything except the filename)
        if '/' in blob_path:
            blob_prefix = '/'.join(blob_path.split('/')[:-1]) + '/'
        else:
            blob_prefix = ""
        
        return container_name, blob_prefix
        
    except Exception as e:
        logger.warning(f"Failed to parse blob URL {blob_url}: {e}")
        return "images", ""  # Default fallback

def convert_json_to_pdf(json_data: dict, output_path: str = None) -> str:
    """
    Convert JSON reimbursement data to PDF report.
    
    Args:
        json_data (dict): The reimbursement data
        output_path (str): Optional output path. If None, generates timestamped filename
        
    Returns:
        str: Path to the generated PDF file
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"reimbursement_report_{timestamp}.pdf"
    
    generator = ReimbursementPDFGenerator()
    generator.generate_pdf_report(json_data, output_path)
    
    return output_path
