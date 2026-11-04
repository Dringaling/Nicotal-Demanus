from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_HEX = r"^#[0-9A-Fa-f]{6}$"

Layout = Literal[
    "title",
    "section",
    "bullets",
    "two_column",
    "table",
    "quote",
    "closing",
]


class Palette(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: str = Field(default="#1B2A4A", pattern=_HEX)
    accent: str = Field(default="#2F6FED", pattern=_HEX)
    text: str = Field(default="#1F2937", pattern=_HEX)
    muted: str = Field(default="#6B7280", pattern=_HEX)
    background: str = Field(default="#FFFFFF", pattern=_HEX)


class BulletItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=220)
    level: int = Field(default=0, ge=0, le=2)

    @field_validator("text")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class Column(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str | None = Field(default=None, max_length=120)
    bullets: list[BulletItem] = Field(default_factory=list, max_length=8)


class TableBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headers: list[str] = Field(min_length=1, max_length=6)
    rows: list[list[str]] = Field(default_factory=list, max_length=8)

    @field_validator("headers")
    @classmethod
    def _headers_not_blank(cls, value: list[str]) -> list[str]:
        cleaned = [header.strip() for header in value]
        if any(not header for header in cleaned):
            raise ValueError("Header không được rỗng")
        return cleaned

    @field_validator("rows")
    @classmethod
    def _rows_clean(cls, value: list[list[str]]) -> list[list[str]]:
        return [[cell.strip() for cell in row] for row in value]

    @model_validator(mode="after")
    def _row_width(self) -> "TableBlock":
        width = len(self.headers)
        for index, row in enumerate(self.rows, start=1):
            if len(row) != width:
                raise ValueError(
                    f"Hàng {index} có {len(row)} ô, cần đúng {width} ô"
                )
        return self


class SlideSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layout: Layout
    title: str = Field(min_length=1, max_length=160)
    subtitle: str | None = Field(default=None, max_length=300)
    bullets: list[BulletItem] = Field(default_factory=list, max_length=8)
    columns: list[Column] = Field(default_factory=list, max_length=2)
    table: TableBlock | None = None
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def _title_strip(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _layout_requirements(self) -> "SlideSpec":
        if self.layout == "table" and self.table is None:
            raise ValueError("layout='table' cần trường 'table'")
        if self.layout == "two_column" and len(self.columns) != 2:
            raise ValueError("layout='two_column' cần đúng 2 cột")
        if self.layout == "bullets" and not self.bullets:
            raise ValueError("layout='bullets' cần ít nhất 1 bullet")
        return self


class DeckSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=300)
    author: str | None = Field(default=None, max_length=120)
    font: str = Field(default="Lexend", min_length=1, max_length=80)
    palette: Palette = Field(default_factory=Palette)
    slides: list[SlideSpec] = Field(min_length=1, max_length=12)
