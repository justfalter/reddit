import collections
from datetime import datetime, timedelta
from pylons import g, c
import time
from r2.models import (Account, Link, Subreddit, Thing, All, DefaultSR,
                       MultiReddit, DomainSR, Friends, ModContribSR,
                       FakeSubreddit, NotFound)
import r2.lib.utils as r2utils

Field = collections.namedtuple("Field", "name cloudsearch_type "
                               "lucene_type function")

SAME_AS_ELASTICSEARCH = object()
FIELD_TYPES = (int, str, datetime, SAME_AS_ELASTICSEARCH, "yesno")

def field(name=None, cloudsearch_type=str, lucene_type=SAME_AS_ELASTICSEARCH):
    if lucene_type is SAME_AS_ELASTICSEARCH:
        lucene_type = cloudsearch_type
    if cloudsearch_type not in FIELD_TYPES + (None,):
        raise ValueError("cloudsearch_type %r not in %r" %
                         (cloudsearch_type, FIELD_TYPES))
    if lucene_type not in FIELD_TYPES + (None,):
        raise ValueError("lucene_type %r not in %r" %
                         (lucene_type, FIELD_TYPES))
    if callable(name):
        # Simple case; decorated as '@field'; act as a decorator instead
        # of a decorator factory
        function = name
        name = None
    else:
        function = None

    def field_inner(fn):
        fn.field = Field(name or fn.func_name, cloudsearch_type,
                         lucene_type, fn)
        return fn

    if function:
        return field_inner(function)
    else:
        return field_inner


class FieldsMeta(type):
    def __init__(cls, name, bases, attrs):
        type.__init__(cls, name, bases, attrs)
        fields = []
        for attr in attrs.itervalues():
            if hasattr(attr, "field"):
                fields.append(attr.field)
        cls._fields = tuple(fields)


class FieldsBase(object):
    __metaclass__ = FieldsMeta

    def fields(self):
        data = {}
        for field in self._fields:
            if field.cloudsearch_type is None:
                continue
            val = field.function(self)
            if val is not None:
                data[field.name] = val
        return data

    @classmethod
    def all_fields(cls):
        return cls._fields

    @classmethod
    def cloudsearch_fields(cls, type_=None, types=FIELD_TYPES):
        types = (type_,) if type_ else types
        return [f for f in cls._fields if f.cloudsearch_type in types]

    @classmethod
    def lucene_fields(cls, type_=None, types=FIELD_TYPES):
        types = (type_,) if type_ else types
        return [f for f in cls._fields if f.lucene_type in types]

    @classmethod
    def cloudsearch_fieldnames(cls, type_=None, types=FIELD_TYPES):
        return [f.name for f in cls.cloudsearch_fields(type_=type_,
                                                       types=types)]

    @classmethod
    def lucene_fieldnames(cls, type_=None, types=FIELD_TYPES):
        return [f.name for f in cls.lucene_fields(type_=type_, types=types)]


class LinkFields(FieldsBase):
    def __init__(self, link, author, sr):
        self.link = link
        self.author = author
        self.sr = sr

    @field(cloudsearch_type=int, lucene_type=None)
    def ups(self):
        return max(0, self.link._ups)

    @field(cloudsearch_type=int, lucene_type=None)
    def downs(self):
        return max(0, self.link._downs)

    @field(cloudsearch_type=int, lucene_type=None)
    def num_comments(self):
        return max(0, getattr(self.link, 'num_comments', 0))

    @field
    def fullname(self):
        return self.link._fullname

    @field
    def subreddit(self):
        return self.sr.name

    @field
    def reddit(self):
        return self.sr.name

    @field
    def title(self):
        return self.link.title

    @field(cloudsearch_type=int)
    def sr_id(self):
        return self.link.sr_id

    @field(cloudsearch_type=int, lucene_type=datetime)
    def timestamp(self):
        return int(time.mktime(self.link._date.utctimetuple()))

    @field(cloudsearch_type=int, lucene_type="yesno")
    def over18(self):
        nsfw = (self.sr.over_18 or self.link.over_18 or
                Link._nsfw.findall(self.link.title))
        return (1 if nsfw else 0)

    @field(cloudsearch_type=None, lucene_type="yesno")
    def nsfw(self):
        return NotImplemented

    @field(cloudsearch_type=int, lucene_type="yesno")
    def is_self(self):
        return (1 if self.link.is_self else 0)

    @field(name="self", cloudsearch_type=None, lucene_type="yesno")
    def self_(self):
        return NotImplemented

    @field
    def author_fullname(self):
        return self.author._fullname

    @field(name="author")
    def author_field(self):
        return '[deleted]' if self.author._deleted else self.author.name

    @field(cloudsearch_type=int)
    def type_id(self):
        return self.link._type_id

    @field
    def site(self):
        if self.link.is_self:
            return g.domain
        else:
            url = r2utils.UrlParser(self.link.url)
            try:
                return list(url.domain_permutations())
            except ValueError:
                return None

    @field
    def selftext(self):
        if self.link.is_self and self.link.selftext:
            return self.link.selftext
        else:
            return None

    @field
    def url(self):
        if not self.link.is_self:
            return self.link.url
        else:
            return None

    @field
    def flair_css_class(self):
        return self.link.flair_css_class

    @field
    def flair_text(self):
        return self.link.flair_text

    @field(cloudsearch_type=None, lucene_type=str)
    def flair(self):
        return NotImplemented


class SubredditFields(FieldsBase):
    def __init__(self, sr):
        self.sr = sr

    @field
    def name(self):
        return self.sr.name

    @field
    def title(self):
        return self.sr.title

    @field(name="type")
    def type_(self):
        return self.sr.type

    @field
    def language(self):
        return self.sr.lang

    @field
    def header_title(self):
        return self.sr.header_title

    @field
    def description(self):
        return self.sr.public_description

    @field
    def sidebar(self):
        return self.sr.description

    @field(cloudsearch_type=int)
    def over18(self):
        return 1 if self.sr.over_18 else 0

    @field
    def link_type(self):
        return self.sr.link_type

    @field
    def activity(self):
        return self.sr._downs

    @field
    def subscribers(self):
        return self.sr._ups

    @field
    def type_id(self):
        return self.sr._type_id


class GenericFieldQuery(object):
    def __init__(self, query_type, name):
        self.query_type = query_type
        self.name = name

class EqualFieldQuery(GenericFieldQuery):
    def __init__(self, name, val, any_word = False):
        self.value = val
        self.any_word = any_word
        super(EqualFieldQuery, self).__init__("equal", name) 

    def __repr__(self):
        '''Return a string representation of this query'''
        result = ["<", self.__class__.__name__, " ", 
            "name:", repr(self.name), " ",
            "value:", repr(self.value), ">"
            ]
        return ''.join(result)

class BooleanFieldQuery(GenericFieldQuery):
    def __init__(self, name, val):
        self.value = (val == True)
        super(BooleanFieldQuery, self).__init__("boolean", name) 

    def __repr__(self):
        '''Return a string representation of this query'''
        result = ["<", self.__class__.__name__, " ", 
            "name:", repr(self.name), " ",
            "value:", repr(self.value), ">"
            ]
        return ''.join(result)

class RangeFieldQuery(GenericFieldQuery):
    def __init__(self, name, range_start=None, range_end=None):
        self.range_start = range_start
        self.range_end = range_end
        super(RangeFieldQuery, self).__init__("range", name)

    def range_start_s(self):
        if self.range_start == None:
            return ''  
        return str(self.range_start)

    def range_end_s(self):
        if self.range_end == None:
            return ''  
        return str(self.range_end)


    def __repr__(self):
        '''Return a string representation of this query'''
        result = ["<", self.__class__.__name__, " ", 
            "name:", repr(self.name), " ",
            "range_start:", repr(self.range_start), " ",
            "range_end:", repr(self.range_end),
            ">"
            ]
        return ''.join(result)

class GenericSort(object):
    def __init__(self, name, ascending, sort_type="generic"):
        self.name = name
        self.sort_type = sort_type
        self.ascending = (ascending == True)

    def __repr__(self):
        '''Return a string representation of this query'''
        result = ["<", self.__class__.__name__, " ", 
            "name:", repr(self.name), " ",
            "ascending:", repr(self.ascending), ">"
            ]
        return ''.join(result)



# In cloudsearch, this is 'text_relevance'.. ElasticSearch: '_score'
class TextRelevanceSort(GenericSort): 
    def __init__(self, ascending = False): 
        super(TextRelevanceSort, self).__init__(None, ascending, 
                                                sort_type="text_relevance")


class GenericSearchQuery(object):
    def __init__(self):
        self.fields = []
        self.sorts = []

    def add_fieldquery(self, fq):
        self.fields.append(fq)

    def add_range(self, name, range_start, range_end):
        self.add_fieldquery(RangeFieldQuery(name, range_start=range_start,
                                       range_end=range_end))
    def add_equal(self, name, val):
        self.add_fieldquery(EqualFieldQuery(name, val))

    def add_equal_any(self, name, val):
        self.add_fieldquery(EqualFieldQuery(name, val, any_word = True))

    def add_boolean(self, name, val):
        self.add_fieldquery(BooleanFieldQuery(name, val))

    def add_sort(self, name, ascending=True):
        self.sorts.append(GenericSort(name, ascending))

    def add_relevance_sort(self, ascending = True):
        self.sorts.append(TextRelevanceSort(ascending))


    def __repr__(self):
        '''Return a string representation of this query'''
        result = ["<", self.__class__.__name__, " ", 
            "fields:", repr(self.fields), " ",
            "sorts:", repr(self.sorts),
            ">"
            ]
        return ''.join(result)

class RelatedArticleSearchQuery(GenericSearchQuery):
    def __init__(self, ts_start, ts_end, title, omit_nsfw=True):
        super(RelatedArticleSearchQuery, self).__init__()
        self.add_range(u"timestamp", ts_start, ts_end)
        self.add_equal_any(u"title", title)

        if omit_nsfw == True:
            self.add_boolean(u"nsfw", False)

        self.add_relevance_sort(False)

class Results(object):
    def __init__(self, docs, hits, facets):
        self.docs = docs
        self.hits = hits
        self._facets = facets
        self._subreddits = []

    def __repr__(self):
        return '%s(%r, %r, %r)' % (self.__class__.__name__,
                                   self.docs,
                                   self.hits,
                                   self._facets)

    @property
    def subreddit_facets(self):
        '''Filter out subreddits that the user isn't allowed to see'''
        if not self._subreddits and 'reddit' in self._facets:
            sr_facets = [(sr['value'], sr['count']) for sr in
                         self._facets['reddit']]

            # look up subreddits
            srs_by_name = Subreddit._by_name([name for name, count
                                              in sr_facets])

            sr_facets = [(srs_by_name[name], count) for name, count
                         in sr_facets if name in srs_by_name]

            # filter by can_view
            self._subreddits = [(sr, count) for sr, count in sr_facets
                                if sr.can_view(c.user)]

        return self._subreddits



