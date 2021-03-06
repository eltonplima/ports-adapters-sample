"""A Flask REST adapter to use as an interface for the application."""

import logging
import threading
from typing import Tuple, Dict, Union

from flask import Flask
from flask_restful import Resource, Api, reqparse
from gevent.pywsgi import WSGIServer

from ..domain.messages import RegisterBookCommand
from ..domain.ports import MessageBus, BookView
from ..settings import identify

LOGGER = logging.getLogger('sample')


class BookResource(Resource):
    """Class to handle incoming REST requests concerning books.

    Extends: Resource

    Methods: get, post
    """

    def __init__(self, bus: MessageBus, view: BookView):
        """BookResource's constructor.

        Params
        ------
        bus -- the message bus to dispatch commands
        view -- the database view to access data
        """
        self.bus = bus
        self.view = view

    def get(self) -> Union[list, Tuple[Dict[str, str], int]]:
        """Returns list of all registered books at database."""
        try:
            books = [b.__dict__ for b in self.view.get_all()]

            if len(books) == 0:
                raise Exception('No books found')

            return books

        except Exception as err:
            return {'error': err.__str__()}, 400

    def post(self) -> Union[Dict[str, str], Tuple[Dict[str, str], int]]:
        """Registers new book at database."""
        parser = reqparse.RequestParser()

        parser.add_argument(
            'isbn', type=str, help='book\'s unique identification'
        )
        parser.add_argument(
            'name', type=str, help='book\'s title'
        )
        parser.add_argument(
            'author', type=str,
            help='the name of the person who wrote the book'
        )
        parser.add_argument(
            'content', type=str, help='whats written on the book'
        )

        args = parser.parse_args(strict=True)

        cmd = RegisterBookCommand(
            args['isbn'], args['name'], args['author'], args['content'])

        try:
            self.bus.handle(cmd)
            return {'message': 'New book registered'}
        except Exception:
            return {'error': 'ISBN already registered to another book'}, 400


class BookIsbnResource(Resource):
    """Class to handle incoming REST requests concerning book visualization by
    ISBN.

    Extends: Resource

    Methods: get
    """

    def __init__(self, view):
        """BookIsbnResource's constructor.

        Params
        ------
        view -- the database view to access data
        """
        self.view = view

    def get(self, isbn: str) -> dict:
        """Returns a book chosen by its ISBN."""
        try:
            return self.view.get_by_isbn(isbn).__dict__
        except:
            return {'error': 'No book with the chosen ISBN found'}, 400


class BookAuthorResource(Resource):
    """Class to handle incoming REST requests concerning book visualization by
    author.

    Extends: Resource

    Methods: get
    """

    def __init__(self, view):
        """BookAuthorResource's constructor.

        Params
        ------
        view -- the database view to access data
        """
        self.view = view

    def get(self, author: str) -> dict:
        """Returns a book chosen by its author."""
        try:
            books = [b.__dict__ for b in self.view.get_by_author(author)]

            if len(books) == 0:
                raise Exception('No book of the chosen author found')

            return books

        except Exception as err:
            return {'error': err.__str__()}, 400


class BookNameResource(Resource):
    """Class to handle incoming REST requests concerning book visualization by
    name.

    Extends: Resource

    Methods: get
    """

    def __init__(self, view):
        """BookNameResource's constructor.

        Params
        ------
        view -- the database view to access data
        """
        self.view = view

    def get(self, name: str) -> dict:
        """Returns a book chosen by its name."""
        try:
            books = [b.__dict__ for b in self.view.get_by_name(name)]

            if len(books) == 0:
                raise Exception('No book with the chosen name found')

            return books

        except Exception as err:
            return {'error': err.__str__()}, 400


@identify('flask', 'interface')
class FlaskInterface(object):
    """Listens to incoming HTTP packages and executes the associated commands.

    Methods: set_message_bus, set_view, start, stop"""

    def __init__(self, cfg):
        """FlaskInterface's constructor.

        Params
        ------
        cfg: dict -- the Flask interface adapter's configuration
        """
        self.host = cfg['host']
        self.port = cfg['port']

        app = Flask(__name__)
        self.api = Api(app)
        self.http_server = WSGIServer((self.host, self.port), app)
        self.thread_server = threading.Thread(
            target=self.http_server.serve_forever)

    def set_message_bus(self, bus):
        """Sets the message bus to be used by the adapter to execute commands.

        Params
        ------
        bus -- the message bus
        """
        self.bus = bus

    def set_view(self, view):
        """Sets the view used to read the database.

        Params
        ------
        view -- the database view
        """
        self.view = view

    def run(self):
        """Method to initialize the adapter by starting the HTTP server."""
        self.api.add_resource(
            BookResource, '/books',
            resource_class_kwargs={'bus': self.bus, 'view': self.view}
        )
        self.api.add_resource(
            BookIsbnResource, '/books/isbn/<string:isbn>',
            resource_class_kwargs={'view': self.view}
        )
        self.api.add_resource(
            BookAuthorResource, '/books/author/<string:author>',
            resource_class_kwargs={'view': self.view}
        )
        self.api.add_resource(
            BookNameResource, '/books/name/<string:name>',
            resource_class_kwargs={'view': self.view}
        )

        LOGGER.info('Starting HTTP server')
        self.thread_server.start()

    def stop(self):
        """Method to stop the HTTP server."""
        LOGGER.info('Stopping HTTP server')
        self.http_server.stop()
        self.thread_server.join()
