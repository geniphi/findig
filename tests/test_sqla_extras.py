#-*- coding: utf-8 -*-
import os
import pytest
import sqlite3
import tempfile
from sqlalchemy.types import *
from sqlalchemy.schema import *
from findig.json import App
from findig.extras.sql import *


@pytest.fixture
def app():
    return App()


@pytest.fixture
def db_file(request):
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_file.close()
    request.addfinalizer(lambda: os.remove(tmp_file.name))
    return tmp_file.name


@pytest.fixture
def db(app, db_file):
    return SQLA("sqlite:///{}".format(db_file), app)


@pytest.fixture
def person_cls(db):
    class Person(db.Base):
        id = Column(Integer, primary_key=True)
        name = Column(Unicode(150), nullable=False)
        age = Column(Integer, nullable=False)
        state = Column(String(2))

    db.create_all()
    return Person


@pytest.fixture
def conn(request, db_file):
    conn = sqlite3.connect(db_file)
    request.addfinalizer(conn.close)
    return conn


@pytest.fixture
def sqla_set(person_cls):
    return SQLASet(person_cls)


def test_add_records(sqla_set, conn, app):
    people = [
        {"name": "Te-jé Rodgers", "age": 25,},
        {"name": "John Smith", "age": 34,},
        {"name": "Terrance Riverdarb", "age": 16,},
        {"name": "Anna Harris", "age": 74,},
        {"name": "Jen Brathwaithe", "age": 32,},
        {"name": "Glen Posner", "age": 52,},
        {"name": "Harriet Peters", "age": 21,},
        {"name": "Anthony Simm", "age": 32,},
        {"name": "שלום привет hello", "age": 49,},
        {"name": b"Jabba", "age": 18,},
    ]

    with app.test_context(create_route=True):
        for person_dict in people:
            sqla_set.add(person_dict)


    queried_people = [
        {"name": record[0], "age": record[1]}
        for record in conn.cursor().execute("Select name, age FROM person")
    ]

    assert people == queried_people

def test_delete_records(sqla_set, conn, app):
    people = [
        {"name": "Te-jé Rodgers", "age": 25,},
        {"name": "John Smith", "age": 34,},
        {"name": "Terrance Riverdarb", "age": 16,},
        {"name": "Anna Harris", "age": 74,},
        {"name": "Jen Brathwaithe", "age": 32,},
        {"name": "Glen Posner", "age": 52,},
        {"name": "Harriet Peters", "age": 21,},
        {"name": "Anthony Simm", "age": 32,},
        {"name": "שלום привет hello", "age": 49,},
        {"name": b"Jabba", "age": 18,},
    ]

    cursor = conn.cursor()
    for person_dict in people:
        cursor.execute("INSERT into person (name, age) VALUES (?, ?)",
                       (person_dict["name"], person_dict["age"]))

    conn.commit()

    with app.test_context(create_route=True):
        for person in sqla_set:
            person.delete()

    assert not list(cursor.execute("SELECT * FROM person"))


def test_sorted_set(sqla_set, conn, app):
    people = [
        {"name": "Te-jé Rodgers", "age": 25,},
        {"name": "John Smith", "age": 34,},
        {"name": "Terrance Riverdarb", "age": 16,},
        {"name": "Anna Harris", "age": 74,},
        {"name": "Jen Brathwaithe", "age": 32,},
        {"name": "Glen Posner", "age": 52,},
        {"name": "Harriet Peters", "age": 21,},
        {"name": "Anthony Simm", "age": 32,},
        {"name": "שלום привет hello", "age": 49,},
        {"name": "Jabba", "age": 18,},
    ]

    cursor = conn.cursor()
    for person_dict in people:
        cursor.execute("INSERT into person (name, age) VALUES (?, ?)",
                       (person_dict["name"], person_dict["age"]))

    conn.commit()

    with app.test_context(create_route=True):
        names = [person["name"] for person in sqla_set.sorted("age", "name")]

    assert names == [
        "Terrance Riverdarb",
        "Jabba",
        "Harriet Peters",
        "Te-jé Rodgers",
        "Anthony Simm",
        "Jen Brathwaithe",
        "John Smith",
        "שלום привет hello",
        "Glen Posner",
        "Anna Harris",
    ]


def test_filtered_set(sqla_set, conn, app, person_cls):
    people = [
        {"name": "Te-jé Rodgers", "age": 25,},
        {"name": "John Smith", "age": 34,},
        {"name": "Terrance Riverdarb", "age": 16,},
        {"name": "Anna Harris", "age": 74,},
        {"name": "Jen Brathwaithe", "age": 32,},
        {"name": "Glen Posner", "age": 52,},
        {"name": "Harriet Peters", "age": 21,},
        {"name": "Anthony Simm", "age": 32,},
        {"name": "שלום привет hello", "age": 49,},
        {"name": "Jabba", "age": 18,},
    ]

    cursor = conn.cursor()
    for person_dict in people:
        cursor.execute("INSERT into person (name, age) VALUES (?, ?)",
                       (person_dict["name"], person_dict["age"]))

    conn.commit()

    with app.test_context(create_route=True):
        assert len(list(sqla_set.filtered(person_cls.age >= 50))) == 2
        assert len(list(sqla_set.filtered(age=32))) == 2


def test_modifier_chain(sqla_set, conn, app, person_cls):
    people = [
        {"name": "Te-jé Rodgers", "age": 25,},
        {"name": "John Smith", "age": 34,},
        {"name": "Terrance Riverdarb", "age": 16,},
        {"name": "Anna Harris", "age": 74,},
        {"name": "Jen Brathwaithe", "age": 32,},
        {"name": "Glen Posner", "age": 52,},
        {"name": "Harriet Peters", "age": 21,},
        {"name": "Anthony Simm", "age": 32,},
        {"name": "שלום привет hello", "age": 49,},
        {"name": "Jabba", "age": 18,},
    ]

    cursor = conn.cursor()
    for person_dict in people:
        cursor.execute("INSERT into person (name, age) VALUES (?, ?)",
                       (person_dict["name"], person_dict["age"]))

    conn.commit()

    with app.test_context(create_route=True):
        five_sorted_names = [
            person["name"] for person in
            sqla_set.sorted("age", "name").limit(5)
        ]

        assert five_sorted_names == [
            "Terrance Riverdarb",
            "Jabba",
            "Harriet Peters",
            "Te-jé Rodgers",
            "Anthony Simm",
        ]

        assert len(list(sqla_set.limit(4).filtered(age=32))) == 0
        assert len(list(sqla_set.limit(5).filtered(age=32))) == 1


def test_fetch_record(sqla_set, conn, app):
    people = [
        {"name": "Te-jé Rodgers", "age": 25,},
        {"name": "John Smith", "age": 34,},
        {"name": "Terrance Riverdarb", "age": 16,},
        {"name": "Anna Harris", "age": 74,},
        {"name": "Jen Brathwaithe", "age": 32,},
        {"name": "Glen Posner", "age": 52,},
        {"name": "Harriet Peters", "age": 21,},
        {"name": "Anthony Simm", "age": 32,},
        {"name": "שלום привет hello", "age": 49,},
        {"name": b"Jabba", "age": 18,},
    ]

    cursor = conn.cursor()
    for person_dict in people:
        cursor.execute("INSERT into person (name, age) VALUES (?, ?)",
                       (person_dict["name"], person_dict["age"]))

    conn.commit()

    with app.test_context(create_route=True):
        person = sqla_set.fetch(age=32)
        assert person["name"] == "Jen Brathwaithe"

def test_update_record(sqla_set, conn, app):
    people = [
        {"name": "Te-jé Rodgers", "age": 25, "state": "NY"},
        {"name": "John Smith", "age": 34, "state": "NY"},
        {"name": "Terrance Riverdarb", "age": 16, "state": "NY"},
        {"name": "Anna Harris", "age": 74, "state": "NY"},
        {"name": "Jen Brathwaithe", "age": 32, "state": "NY"},
        {"name": "Glen Posner", "age": 52, "state": "NY"},
        {"name": "Harriet Peters", "age": 21, "state": "NY"},
        {"name": "Anthony Simm", "age": 32, "state": "NY"},
        {"name": "שלום привет hello", "age": 49, "state": "NY"},
        {"name": b"Jabba", "age": 18, "state": "NY"},
    ]

    cursor = conn.cursor()
    for person_dict in people:
        cursor.execute("INSERT into person (name, age) VALUES (?, ?)",
                       (person_dict["name"], person_dict["age"]))

    conn.commit()

    with app.test_context(create_route=True):
        person = sqla_set.fetch(id=5)
        person.update(age=17, name="Teddy")

    assert cursor.execute(
        "select state,name,age from person where id = 5;"
    ).fetchone() == (None, "Teddy", 17)

def test_patch_record(sqla_set, conn, app):
    people = [
        {"name": "Te-jé Rodgers", "age": 25,},
        {"name": "John Smith", "age": 34,},
        {"name": "Terrance Riverdarb", "age": 16,},
        {"name": "Anna Harris", "age": 74,},
        {"name": "Jen Brathwaithe", "age": 32,},
        {"name": "Glen Posner", "age": 52,},
        {"name": "Harriet Peters", "age": 21,},
        {"name": "Anthony Simm", "age": 32,},
        {"name": "שלום привет hello", "age": 49,},
        {"name": b"Jabba", "age": 18,},
    ]

    cursor = conn.cursor()
    for person_dict in people:
        cursor.execute("INSERT into person (name, age) VALUES (?, ?)",
                       (person_dict["name"], person_dict["age"]))

    conn.commit()

    with app.test_context(create_route=True):
        person = sqla_set.fetch(name="John Smith")
        person.patch(dict(id=1000, state="CO"), ())

    assert cursor.execute(
        "select state,name,age from person where id = 1000;"
    ).fetchone() == ("CO", "John Smith", 34)
