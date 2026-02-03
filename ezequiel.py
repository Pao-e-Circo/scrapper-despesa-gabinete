from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import os
import sqlalchemy
from sqlalchemy.orm import Session
import re
from datetime import datetime
from decimal import Decimal
import difflib
import uuid
from datetime import date

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from sqlalchemy.dialects.postgresql import UUID

class Base(DeclarativeBase):
    pass

class Councilour(Base):
    __tablename__ = "councilours"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sqlalchemy.String, nullable=False)
    phone: Mapped[str] = mapped_column(sqlalchemy.String, nullable=True)
    email: Mapped[str] = mapped_column(sqlalchemy.String, nullable=False)
    photo_url: Mapped[str] = mapped_column(sqlalchemy.String, nullable=False)
    party: Mapped[str] = mapped_column(sqlalchemy.String, nullable=False)

    attendances: Mapped[list["Attendence"]] = relationship(back_populates="councilour")

class Attendence(Base):
    __tablename__ = "attendences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    councilor_id: Mapped[uuid.UUID] = mapped_column(sqlalchemy.ForeignKey("councilours.id"), nullable=False)
    month: Mapped[date] = mapped_column(sqlalchemy.Date, nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)

    councilour: Mapped["Councilour"] = relationship(back_populates="attendances")

class OfficeSpending(Base):
    __tablename__ = "office_spendings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    councilor_id: Mapped[uuid.UUID] = mapped_column(sqlalchemy.ForeignKey("councilours.id"), nullable=False)
    month: Mapped[date] = mapped_column(sqlalchemy.Date, nullable=False)
    materials: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False, default=Decimal(0))
    mobile_phone: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False, default=Decimal(0))
    fixed_phone: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False, default=Decimal(0))
    paper: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False, default=Decimal(0))
    airline_tickets: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False, default=Decimal(0))
    hotel_rate: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False, default=Decimal(0))
    gasoline: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False, default=Decimal(0))


def get_councilour_by_name_and_set_id(name: str, councilours: list[Councilour]):
    names = [c.name for c in councilours]
    match = difflib.get_close_matches(name, names, n=1, cutoff=0.7)
    if match:
        return next((c for c in councilours if c.name == match[0]), None)
    return None

def parse_raw_string_to_office_spending_schema(text: str) -> list[OfficeSpending]:
    lines = text.split('\n')

    year_match = re.search(r'RELATÓRIO DE DESPESA ANUAL - (\d{4})', text)
    year = int(year_match.group(1)) if year_match else datetime.now().year

    councilor_name_match = re.search(r'Gabinete Vereador[a]?\s(.+)', text)
    councilor_name = councilor_name_match.group(1).strip() if councilor_name_match else "N/A"

    data_lines = lines[5:]

    spendings_by_month = {}

    for line in data_lines:
        if 'TOTAIS MÊS' in line:
            continue

        parts = re.split(r'\s+R\$\s+', line)
        item_name = parts[0].strip()
        values_str = [v for v in parts[1:] if re.match(r'[\d.,]+', v)]

        # Remove os dois últimos valores (Média e Total)
        monthly_values_str = values_str[:-2]

        for i, value_str in enumerate(monthly_values_str):
            month = i + 1
            value = Decimal(value_str.replace('.', '').replace(',', '.'))

            if month not in spendings_by_month:
                spendings_by_month[month] = OfficeSpending(
                    month=datetime(year, month, 1).date(),
                    # O councilor_id será definido posteriormente
                )
                # Atribui o nome extraído para uso posterior
                spendings_by_month[month].councilor_name_temp = councilor_name

            if 'Materiais de Expediente' in item_name: spendings_by_month[month].materials = value
            elif 'Telefonia Móvel' in item_name: spendings_by_month[month].mobile_phone = value
            elif 'Telefonia Fixa' in item_name: spendings_by_month[month].fixed_phone = value
            elif 'Fotocópias' in item_name: spendings_by_month[month].paper = value
            elif 'Passagens' in item_name: spendings_by_month[month].airline_tickets = value
            elif 'Diárias' in item_name: spendings_by_month[month].hotel_rate = value
            elif 'Combustíveis' in item_name: spendings_by_month[month].gasoline = value

    return list(spendings_by_month.values())

def save_office_spendings_for_each_councilour(client: sqlalchemy.Engine, strings: list[str], councilours: list[Councilour]):
    office_spendings = []

    for i in strings:
        office_spendings.extend(parse_raw_string_to_office_spending_schema(i))

    for spending in office_spendings:
        councilour = get_councilour_by_name_and_set_id(spending.councilor_name_temp, councilours)
        if councilour:
            spending.councilor_id = councilour.id
        else:
            print(f"Vereador '{spending.councilor_name_temp}' não encontrado. O registro de despesa será ignorado.")

    # Filtra apenas os registros que tiveram um vereador correspondente encontrado
    potential_spendings = [s for s in office_spendings if hasattr(s, 'councilor_id')]

    councilor_ids = list({s.councilor_id for s in potential_spendings})
    existing_spendings = get_office_spendings_for_councilors(client, councilor_ids)
    existing_keys = {(s.councilor_id, s.month) for s in existing_spendings}

    spendings_to_save = []
    for spending in potential_spendings:
        if (spending.councilor_id, spending.month) not in existing_keys:
            spendings_to_save.append(spending)

    if not spendings_to_save:
        print('Nenhum novo registro de despesa para salvar.')
        return

    print(f'Iniciando inserção de {len(spendings_to_save)} registros de despesas para o mês de {spendings_to_save[0].month}')
    print('Pressiona qualquer tecla para prosseguir.')
    input()

    with Session(client) as session:
        session.add_all(spendings_to_save)
        session.commit()

    print('Registros de despesas inseridas com sucesso.')

def get_all_councilours(client: sqlalchemy.Engine):
    with Session(client) as session:
        stmt = sqlalchemy.select(Councilour)
        return session.scalars(stmt).all()
    
def get_office_spendings_for_councilors(client: sqlalchemy.Engine, councilor_ids: list[uuid.UUID]):
    with Session(client) as session:
        stmt = sqlalchemy.select(OfficeSpending).where(OfficeSpending.councilor_id.in_(councilor_ids))
        return session.scalars(stmt).all()

txt_file = os.getenv("despesas_txt_path")
if txt_file is None:
    print("A variável de ambiente 'paoecirco.org_link.txt_path' não está definida.")

links = []

with open(txt_file, "r") as f:
    for line in f:
        links.append(line.strip())

options = Options()
options.binary_location = "/usr/bin/chromium"
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage") # TODO ver isso, desabilita browser sandbox, essa flag não pode ser usado em PRD

service = Service("/usr/bin/chromedriver")

driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 10)

strings = []

print('Iniciando o scrapping dos relatórios de despesas.')
for link in links:
    driver.get(link)

    wait.until(EC.presence_of_element_located((By.ID, "pageswitcher-content")))

    iframe = driver.find_element(By.ID, "pageswitcher-content")
    driver.switch_to.frame(iframe)

    parent = driver.find_element(By.XPATH, "/html/body/div/div/div[1]/table/tbody")
    strings.append(parent.text)
    print(parent.text)

driver.quit()

print('Scrapping finalizado, iniciando inserção na base de dados.')

client = sqlalchemy.create_engine(
    "postgresql+psycopg2://postgres:postgres@server-database-1:5432/paoecirco.org",
    echo=False
)

Base.metadata.create_all(client)

councilours = get_all_councilours(client)
save_office_spendings_for_each_councilour(client, strings, councilours)