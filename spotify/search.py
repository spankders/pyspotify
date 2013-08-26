from __future__ import unicode_literals

import collections
import logging
import threading
import uuid

import spotify
from spotify import ffi, lib, utils


__all__ = [
    'SearchResult',
    'SearchResultPlaylist',
    'SearchType',
]

logger = logging.getLogger(__name__)


class SearchResult(object):
    """A Spotify search result.

    Call the :meth:`~Session.search` method on your :class:`Session` instance
    to do a search and get a :class:`SearchResult` back.
    """

    def __init__(
            self, query='', callback=None,
            track_offset=0, track_count=20,
            album_offset=0, album_count=20,
            artist_offset=0, artist_count=20,
            playlist_offset=0, playlist_count=20,
            search_type=None,
            sp_search=None, add_ref=True):

        self.callback = callback
        self.track_offset = track_offset
        self.track_count = track_count
        self.album_offset = album_offset
        self.album_count = album_count
        self.artist_offset = artist_offset
        self.artist_count = artist_count
        self.playlist_offset = playlist_offset
        self.playlist_count = playlist_count
        self.search_type = search_type

        self.complete_event = threading.Event()

        if sp_search is None:
            if search_type is None:
                search_type = SearchType.STANDARD
            query = ffi.new('char[]', utils.to_bytes(query))

            key = utils.to_bytes(uuid.uuid4().hex)
            assert key not in spotify.callback_dict
            userdata = ffi.new('char[32]', key)

            spotify.callback_dict[key] = (callback, self)

            sp_search = lib.sp_search_create(
                spotify.session_instance._sp_session, query,
                track_offset, track_count,
                album_offset, album_count,
                artist_offset, artist_count,
                playlist_offset, playlist_count,
                int(search_type), _search_complete_callback, userdata)
            add_ref = False

        if add_ref:
            lib.sp_search_add_ref(sp_search)
        self._sp_search = ffi.gc(sp_search, lib.sp_search_release)

    complete_event = None
    """:class:`threading.Event` that is set when the search is completed."""

    @property
    def is_loaded(self):
        """Whether the search's data is loaded."""
        return bool(lib.sp_search_is_loaded(self._sp_search))

    @property
    def error(self):
        """An :class:`ErrorType` associated with the search.

        Check to see if there was problems loading the search.
        """
        return spotify.ErrorType(lib.sp_search_error(self._sp_search))

    def load(self, timeout=None):
        """Block until the search's data is loaded.

        :param timeout: seconds before giving up and raising an exception
        :type timeout: float
        :returns: self
        """
        # TODO Replace with self.complete_event.wait(timeout) when we have a
        # thread that takes care of all ``process_events()`` calls for us.
        return utils.load(self, timeout=timeout)

    @property
    def query(self):
        """The search query.

        Will always return :class:`None` if the search isn't loaded.
        """
        spotify.Error.maybe_raise(self.error)
        query = utils.to_unicode(lib.sp_search_query(self._sp_search))
        return query if query else None

    @property
    def did_you_mean(self):
        """The search's "did you mean" query or :class:`None` if no such
        suggestion exists.

        Will always return :class:`None` if the search isn't loaded.
        """
        spotify.Error.maybe_raise(self.error)
        did_you_mean = utils.to_unicode(
            lib.sp_search_did_you_mean(self._sp_search))
        return did_you_mean if did_you_mean else None

    @property
    def tracks(self):
        """The tracks matching the search query.

        Will always return an empty list if the search isn't loaded.
        """
        spotify.Error.maybe_raise(self.error)
        if not self.is_loaded:
            return []
        lib.sp_search_add_ref(self._sp_search)
        return utils.Sequence(
            sp_obj=ffi.gc(self._sp_search, lib.sp_search_release),
            len_func=lib.sp_search_num_tracks,
            getitem_func=(
                lambda sp_search, key:
                spotify.Track(sp_track=lib.sp_search_track(sp_search, key))))

    @property
    def track_total(self):
        """The total number of tracks matching the search query.

        If the number is larger than the interval specified at search object
        creation, more search results are available. To fetch these, create a
        new search object with a new interval.
        """
        spotify.Error.maybe_raise(self.error)
        return lib.sp_search_total_tracks(self._sp_search)

    @property
    def albums(self):
        """The albums matching the search query.

        Will always return an empty list if the search isn't loaded.
        """
        spotify.Error.maybe_raise(self.error)
        if not self.is_loaded:
            return []
        lib.sp_search_add_ref(self._sp_search)
        return utils.Sequence(
            sp_obj=ffi.gc(self._sp_search, lib.sp_search_release),
            len_func=lib.sp_search_num_albums,
            getitem_func=(
                lambda sp_search, key:
                spotify.Album(sp_album=lib.sp_search_album(sp_search, key))))

    @property
    def album_total(self):
        """The total number of albums matching the search query.

        If the number is larger than the interval specified at search object
        creation, more search results are available. To fetch these, create a
        new search object with a new interval.
        """
        spotify.Error.maybe_raise(self.error)
        return lib.sp_search_total_albums(self._sp_search)

    @property
    def artists(self):
        """The artists matching the search query.

        Will always return an empty list if the search isn't loaded.
        """
        spotify.Error.maybe_raise(self.error)
        if not self.is_loaded:
            return []
        lib.sp_search_add_ref(self._sp_search)
        return utils.Sequence(
            sp_obj=ffi.gc(self._sp_search, lib.sp_search_release),
            len_func=lib.sp_search_num_artists,
            getitem_func=(
                lambda sp_search, key:
                spotify.Artist(
                    sp_artist=lib.sp_search_artist(sp_search, key))))

    @property
    def artist_total(self):
        """The total number of artists matching the search query.

        If the number is larger than the interval specified at search object
        creation, more search results are available. To fetch these, create a
        new search object with a new interval.
        """
        spotify.Error.maybe_raise(self.error)
        return lib.sp_search_total_artists(self._sp_search)

    @property
    def playlists(self):
        """The playlists matching the search query as
        :class:`SearchResultPlaylist` objects containing the name, URI and
        image URI for matching playlists.

        Will always return an empty list if the search isn't loaded.
        """
        spotify.Error.maybe_raise(self.error)
        if not self.is_loaded:
            return []

        def getitem(sp_search, key):
            return spotify.SearchResultPlaylist(
                name=utils.to_unicode(
                    lib.sp_search_playlist_name(self._sp_search, key)),
                uri=utils.to_unicode(
                    lib.sp_search_playlist_uri(self._sp_search, key)),
                image_uri=utils.to_unicode(
                    lib.sp_search_playlist_image_uri(self._sp_search, key)))

        lib.sp_search_add_ref(self._sp_search)
        return utils.Sequence(
            sp_obj=ffi.gc(self._sp_search, lib.sp_search_release),
            len_func=lib.sp_search_num_playlists,
            getitem_func=getitem)

    @property
    def playlist_total(self):
        """The total number of playlists matching the search query.

        If the number is larger than the interval specified at search object
        creation, more search results are available. To fetch these, create a
        new search object with a new interval.
        """
        spotify.Error.maybe_raise(self.error)
        return lib.sp_search_total_playlists(self._sp_search)

    def more(
            self, callback=None,
            track_count=None, album_count=None, artist_count=None,
            playlist_count=None):
        """Get the next page of search results for the same query.

        If called without arguments, the ``callback`` and ``*_count`` arguments
        from the original search is reused. If anything other than
        :class:`None` is specified, the value is used instead.
        """
        callback = callback or self.callback
        track_offset = self.track_offset + self.track_count
        track_count = track_count or self.track_count
        album_offset = self.album_offset + self.album_count
        album_count = album_count or self.album_count
        artist_offset = self.artist_offset + self.artist_count
        artist_count = artist_count or self.artist_count
        playlist_offset = self.playlist_offset + self.playlist_count
        playlist_count = playlist_count or self.playlist_count

        return SearchResult(
            query=self.query, callback=callback,
            track_offset=track_offset, track_count=track_count,
            album_offset=album_offset, album_count=album_count,
            artist_offset=artist_offset, artist_count=artist_count,
            playlist_offset=playlist_offset, playlist_count=playlist_count,
            search_type=self.search_type)

    @property
    def link(self):
        """A :class:`Link` to the search."""
        return spotify.Link(self)


@ffi.callback('void(sp_search *, void *)')
def _search_complete_callback(sp_search, userdata):
    logger.debug('search_complete_callback called')
    if userdata is ffi.NULL:
        logger.warning('search_complete_callback called without userdata')
        return
    key = ffi.string(ffi.cast('char[32]', userdata))
    value = spotify.callback_dict.pop(key, None)
    if value is None:
        logger.warning(
            'search_complete_callback key %r not in callback_dict: %r',
            key, spotify.callback_dict.keys())
        return
    (callback, search_result) = value
    search_result.complete_event.set()
    if callback is not None:
        callback(search_result)


class SearchResultPlaylist(collections.namedtuple(
        'SearchResultPlaylist', ['name', 'uri', 'image_uri'])):
    """A playlist matching a search query."""
    pass


@utils.make_enum('SP_SEARCH_')
class SearchType(utils.IntEnum):
    pass