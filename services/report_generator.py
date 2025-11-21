import os
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

class TokenReportGenerator:
    """Генератор отчетов по использованию токенов"""
    
    def __init__(self, tokens_file: str = "tokens.txt"):
        self.tokens_file = tokens_file
    
    def parse_tokens_file(self, year: int, month: int) -> Dict[str, Dict[str, any]]:
        """
        Парсит файл tokens.txt и группирует данные по пользователям за указанный месяц
        
        Возвращает:
        {
            "user_id": {
                "user_name": "John",
                "input_tokens": 1000,
                "output_tokens": 500,
                "total_tokens": 1500
            }
        }
        """
        users_data = defaultdict(lambda: {
            "user_name": "Unknown",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0
        })
        
        if not os.path.exists(self.tokens_file):
            return dict(users_data)
        
        try:
            with open(self.tokens_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        # Формат: [2025-11-21 15:30:45] user_id/user_name/input/output/total
                        if "]" in line:
                            timestamp_part, data_part = line.split("]", 1)
                            timestamp_str = timestamp_part.strip("[]").strip()
                            
                            # Проверяем месяц и год
                            log_date = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                            if log_date.year != year or log_date.month != month:
                                continue
                            
                            # Парсим данные
                            data_part = data_part.strip()
                            parts = data_part.split("/")
                            
                            if len(parts) >= 5:
                                user_id = parts[0].strip()
                                user_name = parts[1].strip()
                                input_tokens = int(parts[2].strip())
                                output_tokens = int(parts[3].strip())
                                total_tokens = int(parts[4].strip())
                                
                                # Суммируем токены
                                users_data[user_id]["user_name"] = user_name
                                users_data[user_id]["input_tokens"] += input_tokens
                                users_data[user_id]["output_tokens"] += output_tokens
                                users_data[user_id]["total_tokens"] += total_tokens
                    
                    except Exception as e:
                        # Пропускаем некорректные строки
                        continue
        
        except Exception as e:
            print(f"Ошибка чтения файла токенов: {e}")
        
        return dict(users_data)
    
    def generate_pdf_report(self, year: int, month: int) -> BytesIO:
        """
        Генерирует PDF отчет за указанный месяц
        
        Возвращает BytesIO с PDF файлом
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        # Стили
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=1  # Центрирование
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12
        )
        
        normal_style = styles['Normal']
        
        # Получаем данные
        users_data = self.parse_tokens_file(year, month)
        
        # Формируем контент
        content = []
        
        # Заголовок
        month_name_ru = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ][month - 1]
        
        title = Paragraph(
            f"<b>Отчет по использованию токенов</b><br/>{month_name_ru} {year}",
            title_style
        )
        content.append(title)
        content.append(Spacer(1, 0.3*inch))
        
        # Если нет данных
        if not users_data:
            no_data = Paragraph("За указанный период данные отсутствуют.", normal_style)
            content.append(no_data)
        else:
            # Сортируем по общему количеству токенов (по убыванию)
            sorted_users = sorted(
                users_data.items(),
                key=lambda x: x[1]['total_tokens'],
                reverse=True
            )
            
            # Общая статистика
            total_input = sum(u[1]['input_tokens'] for u in sorted_users)
            total_output = sum(u[1]['output_tokens'] for u in sorted_users)
            total_all = sum(u[1]['total_tokens'] for u in sorted_users)
            
            summary = Paragraph(
                f"<b>Общая статистика:</b> {len(users_data)} пользователей, "
                f"{total_all:,} токенов",
                heading_style
            )
            content.append(summary)
            content.append(Spacer(1, 0.2*inch))
            
            # Данные по каждому пользователю
            for user_id, data in sorted_users:
                content.append(Paragraph("=" * 80, normal_style))
                content.append(Spacer(1, 0.1*inch))
                
                user_header = Paragraph(
                    f"<b>Пользователь:</b> {data['user_name']} (ID: {user_id})",
                    heading_style
                )
                content.append(user_header)
                
                # Таблица с токенами
                token_data = [
                    ['Тип токенов', 'Количество'],
                    ['Входных токенов', f"{data['input_tokens']:,}"],
                    ['Выходных токенов', f"{data['output_tokens']:,}"],
                    ['Общее количество', f"<b>{data['total_tokens']:,}</b>"]
                ]
                
                token_table = Table(token_data, colWidths=[3*inch, 2*inch])
                token_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ]))
                
                content.append(token_table)
                content.append(Spacer(1, 0.3*inch))
        
        # Футер
        content.append(Spacer(1, 0.5*inch))
        footer_text = f"Отчет сгенерирован: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        footer = Paragraph(f"<i>{footer_text}</i>", normal_style)
        content.append(footer)
        
        # Генерируем PDF
        doc.build(content)
        buffer.seek(0)
        
        return buffer

# Глобальный экземпляр генератора
report_generator = TokenReportGenerator()

