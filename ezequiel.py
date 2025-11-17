from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import os
from datetime import date

import sqlalchemy
from sqlalchemy import select, exists
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, relationship
from sqlalchemy.dialects.postgresql import UUID

class Base(DeclarativeBase):
    pass

class OfficeSpending(Base):
    __tablename__ = "office_spendings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    month: Mapped[date] = mapped_column(sqlalchemy.Date, nullable=False)
    materials: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False)
    mobile_phone: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False)
    fixed_phone: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False)
    paper: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False)
    airline_tickets: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False)
    hotel_rate: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False)
    gasoline: Mapped[Decimal] = mapped_column(sqlalchemy.Numeric(10, 2), nullable=False)

    councilour: Mapped[["Councilour"]] = relationship(back_populates="councilour")

txt_file = os.getenv("paoecirco.org_link.txt_path")

links = []

with open(txt_file, "r") as f:
    for line in f:
        links.append(line.strip())

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
wait = WebDriverWait(driver, 10)

for link in links: # TODO add try/catch with logs
    driver.get(link)

    wait.until(EC.presence_of_element_located((By.ID, "pageswitcher-content")))

    iframe = driver.find_element(By.ID, "pageswitcher-content")
    driver.switch_to.frame(iframe)

    parent = driver.find_element(By.XPATH, "/html/body/div/div/div[1]/table/tbody") 
    print(parent.text)


driver.quit()