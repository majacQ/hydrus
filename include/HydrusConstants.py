import os
import sys

# dirs

BASE_DIR = sys.path[0]

BIN_DIR = BASE_DIR + os.path.sep + 'bin'
DB_DIR = BASE_DIR + os.path.sep + 'db'
CLIENT_ARCHIVES_DIR = DB_DIR + os.path.sep + 'client_archives'
CLIENT_FILES_DIR = DB_DIR + os.path.sep + 'client_files'
SERVER_FILES_DIR = DB_DIR + os.path.sep + 'server_files'
CLIENT_THUMBNAILS_DIR = DB_DIR + os.path.sep + 'client_thumbnails'
SERVER_THUMBNAILS_DIR = DB_DIR + os.path.sep + 'server_thumbnails'
SERVER_MESSAGES_DIR = DB_DIR + os.path.sep + 'server_messages'
CLIENT_UPDATES_DIR = DB_DIR + os.path.sep + 'client_updates'
SERVER_UPDATES_DIR = DB_DIR + os.path.sep + 'server_updates'
LOGS_DIR = BASE_DIR + os.path.sep + 'logs'
STATIC_DIR = BASE_DIR + os.path.sep + 'static'

#

PLATFORM_WINDOWS = False
PLATFORM_OSX  = False
PLATFORM_LINUX = False

if sys.platform == 'win32': PLATFORM_WINDOWS = True
elif sys.platform == 'darwin': PLATFORM_OSX = True
elif sys.platform == 'linux2': PLATFORM_LINUX = True

#if PLATFORM_LINUX:
#    
#    if not hasattr( sys, 'frozen' ):
#        
#        import wxversion
#        
#        if not wxversion.checkInstalled( '2.9' ): raise Exception( 'Need wxPython 2.9 on Linux!' )
#        
#        wxversion.select( '2.9' )
#        

import wx
import sqlite3
import traceback
import yaml

options = {}

# Misc

NETWORK_VERSION = 16
SOFTWARE_VERSION = 161

UNSCALED_THUMBNAIL_DIMENSIONS = ( 200, 200 )

HYDRUS_KEY_LENGTH = 32

UPDATE_DURATION = 100000

lifetimes = [ ( 'one month', 31 * 86400 ), ( 'three months', 3 * 31 * 86400 ), ( 'six months', 6 * 31 * 86400 ), ( 'one year', 12 * 31 * 86400 ), ( 'two years', 24 * 31 * 86400 ), ( 'five years', 60 * 31 * 86400 ), ( 'does not expire', None ) ]

# Enums

CONTENT_DATA_TYPE_MAPPINGS = 0
CONTENT_DATA_TYPE_TAG_SIBLINGS = 1
CONTENT_DATA_TYPE_TAG_PARENTS = 2
CONTENT_DATA_TYPE_FILES = 3
CONTENT_DATA_TYPE_RATINGS = 4

CONTENT_UPDATE_ADD = 0
CONTENT_UPDATE_DELETE = 1
CONTENT_UPDATE_PENDING = 2
CONTENT_UPDATE_RESCIND_PENDING = 3
CONTENT_UPDATE_PETITION = 4
CONTENT_UPDATE_RESCIND_PETITION = 5
CONTENT_UPDATE_EDIT_LOG = 6
CONTENT_UPDATE_ARCHIVE = 7
CONTENT_UPDATE_INBOX = 8
CONTENT_UPDATE_RATING = 9
CONTENT_UPDATE_DENY_PEND = 11
CONTENT_UPDATE_DENY_PETITION = 12
CONTENT_UPDATE_ADVANCED = 13

content_update_string_lookup = {}

content_update_string_lookup[ CONTENT_UPDATE_ADD ] = 'add'
content_update_string_lookup[ CONTENT_UPDATE_DELETE ] = 'delete'
content_update_string_lookup[ CONTENT_UPDATE_PENDING ] = 'pending'
content_update_string_lookup[ CONTENT_UPDATE_RESCIND_PENDING ] = 'rescind pending'
content_update_string_lookup[ CONTENT_UPDATE_PETITION ] = 'petition'
content_update_string_lookup[ CONTENT_UPDATE_RESCIND_PETITION ] = 'rescind petition'
content_update_string_lookup[ CONTENT_UPDATE_EDIT_LOG ] = 'edit log'
content_update_string_lookup[ CONTENT_UPDATE_ARCHIVE ] = 'archive'
content_update_string_lookup[ CONTENT_UPDATE_INBOX ] = 'inbox'
content_update_string_lookup[ CONTENT_UPDATE_RATING ] = 'rating'
content_update_string_lookup[ CONTENT_UPDATE_DENY_PEND ] = 'deny pend'
content_update_string_lookup[ CONTENT_UPDATE_DENY_PETITION ] = 'deny petition'

IMPORT_FOLDER_TYPE_DELETE = 0
IMPORT_FOLDER_TYPE_SYNCHRONISE = 1

EXPORT_FOLDER_TYPE_REGULAR = 0
EXPORT_FOLDER_TYPE_SYNCHRONISE = 1

GET_DATA = 0
POST_DATA = 1
POST_PETITIONS = 2
RESOLVE_PETITIONS = 3
MANAGE_USERS = 4
GENERAL_ADMIN = 5
EDIT_SERVICES = 6
UNKNOWN_PERMISSION = 7

CREATABLE_PERMISSIONS = [ GET_DATA, POST_DATA, POST_PETITIONS, RESOLVE_PETITIONS, MANAGE_USERS, GENERAL_ADMIN ]
ADMIN_PERMISSIONS = [ RESOLVE_PETITIONS, MANAGE_USERS, GENERAL_ADMIN, EDIT_SERVICES ]

permissions_string_lookup = {}

permissions_string_lookup[ GET_DATA ] = 'get data'
permissions_string_lookup[ POST_DATA ] = 'post data'
permissions_string_lookup[ POST_PETITIONS ] = 'post petitions'
permissions_string_lookup[ RESOLVE_PETITIONS ] = 'resolve petitions'
permissions_string_lookup[ MANAGE_USERS ] = 'manage users'
permissions_string_lookup[ GENERAL_ADMIN ] = 'general administration'
permissions_string_lookup[ EDIT_SERVICES ] = 'edit services'
permissions_string_lookup[ UNKNOWN_PERMISSION ] = 'unknown'

TAG_REPOSITORY = 0
FILE_REPOSITORY = 1
LOCAL_FILE = 2
MESSAGE_DEPOT = 3
LOCAL_TAG = 5
LOCAL_RATING_NUMERICAL = 6
LOCAL_RATING_LIKE = 7
RATING_NUMERICAL_REPOSITORY = 8
RATING_LIKE_REPOSITORY = 9
COMBINED_TAG = 10
COMBINED_FILE = 11
LOCAL_BOORU = 12
SERVER_ADMIN = 99
NULL_SERVICE = 100

service_string_lookup = {}

service_string_lookup[ TAG_REPOSITORY ] = 'hydrus tag repository'
service_string_lookup[ FILE_REPOSITORY ] = 'hydrus file repository'
service_string_lookup[ LOCAL_FILE ] = 'hydrus local file service'
service_string_lookup[ MESSAGE_DEPOT ] = 'hydrus message depot'
service_string_lookup[ LOCAL_TAG ] = 'local tag service'
service_string_lookup[ LOCAL_RATING_NUMERICAL ] = 'local numerical rating service'
service_string_lookup[ LOCAL_RATING_LIKE ] = 'local like/dislike rating service'
service_string_lookup[ RATING_NUMERICAL_REPOSITORY ] = 'hydrus numerical rating repository'
service_string_lookup[ RATING_LIKE_REPOSITORY ] = 'hydrus like/dislike rating repository'
service_string_lookup[ COMBINED_TAG ] = 'virtual combined tag service'
service_string_lookup[ COMBINED_FILE ] = 'virtual combined file service'
service_string_lookup[ LOCAL_BOORU ] = 'hydrus local booru'
service_string_lookup[ SERVER_ADMIN ] = 'hydrus server administration'
service_string_lookup[ NULL_SERVICE ] = 'null service'

RATINGS_SERVICES = [ LOCAL_RATING_LIKE, LOCAL_RATING_NUMERICAL, RATING_LIKE_REPOSITORY, RATING_NUMERICAL_REPOSITORY ]
REPOSITORIES = [ TAG_REPOSITORY, FILE_REPOSITORY, RATING_LIKE_REPOSITORY, RATING_NUMERICAL_REPOSITORY ]
RESTRICTED_SERVICES = ( REPOSITORIES ) + [ SERVER_ADMIN, MESSAGE_DEPOT ]
REMOTE_SERVICES = list( RESTRICTED_SERVICES )
TAG_SERVICES = [ LOCAL_TAG, TAG_REPOSITORY ]
LOCAL_SERVICES = [ LOCAL_FILE, LOCAL_TAG, LOCAL_RATING_LIKE, LOCAL_RATING_NUMERICAL, LOCAL_BOORU, COMBINED_FILE, COMBINED_TAG ]
NONEDITABLE_SERVICES = [ LOCAL_BOORU, LOCAL_FILE, LOCAL_TAG ]
ALL_SERVICES = list( REMOTE_SERVICES ) + list( LOCAL_SERVICES )

SERVICES_WITH_THUMBNAILS = [ FILE_REPOSITORY, LOCAL_FILE ]

DELETE_FILES_PETITION = 0
DELETE_TAG_PETITION = 1

BAN = 0
SUPERBAN = 1
CHANGE_ACCOUNT_TYPE = 2
ADD_TO_EXPIRES = 3
SET_EXPIRES = 4

CURRENT = 0
PENDING = 1
DELETED = 2
PETITIONED = 3
DELETED_PENDING = 4

HIGH_PRIORITY = 0
LOW_PRIORITY = 2

SCORE_PETITION = 0

SERVICE_INFO_NUM_FILES = 0
SERVICE_INFO_NUM_INBOX = 1
SERVICE_INFO_NUM_LOCAL = 2
SERVICE_INFO_NUM_MAPPINGS = 3
SERVICE_INFO_NUM_DELETED_MAPPINGS = 4
SERVICE_INFO_NUM_DELETED_FILES = 5
SERVICE_INFO_NUM_THUMBNAILS = 6
SERVICE_INFO_NUM_THUMBNAILS_LOCAL = 7
SERVICE_INFO_TOTAL_SIZE = 8
SERVICE_INFO_NUM_NAMESPACES = 9
SERVICE_INFO_NUM_TAGS = 10
SERVICE_INFO_NUM_PENDING = 11
SERVICE_INFO_NUM_CONVERSATIONS = 12
SERVICE_INFO_NUM_UNREAD = 13
SERVICE_INFO_NUM_DRAFTS = 14
SERVICE_INFO_NUM_PENDING_MAPPINGS = 15
SERVICE_INFO_NUM_PETITIONED_MAPPINGS = 16
SERVICE_INFO_NUM_PENDING_FILES = 15
SERVICE_INFO_NUM_PETITIONED_FILES = 16
SERVICE_INFO_NUM_PENDING_TAG_SIBLINGS = 17
SERVICE_INFO_NUM_PETITIONED_TAG_SIBLINGS = 18
SERVICE_INFO_NUM_PENDING_TAG_PARENTS = 19
SERVICE_INFO_NUM_PETITIONED_TAG_PARENTS = 20
SERVICE_INFO_NUM_SHARES = 21

SERVICE_UPDATE_ACCOUNT = 0
SERVICE_UPDATE_DELETE_PENDING = 1
SERVICE_UPDATE_ERROR = 2
SERVICE_UPDATE_BEGIN_END = 3
SERVICE_UPDATE_RESET = 4
SERVICE_UPDATE_REQUEST_MADE = 5
SERVICE_UPDATE_LAST_CHECK = 6
SERVICE_UPDATE_NEWS = 7
SERVICE_UPDATE_NEXT_DOWNLOAD_TIMESTAMP = 8
SERVICE_UPDATE_NEXT_PROCESSING_TIMESTAMP = 9
SERVICE_UPDATE_SUBINDEX_COUNT = 10

ADD = 0
DELETE = 1
EDIT = 2
SET = 3

APPROVE = 0
DENY = 1

GET = 0
POST = 1
OPTIONS = 2

APPLICATION_HYDRUS_CLIENT_COLLECTION = 0
IMAGE_JPEG = 1
IMAGE_PNG = 2
IMAGE_GIF = 3
IMAGE_BMP = 4
APPLICATION_FLASH = 5
APPLICATION_YAML = 6
IMAGE_ICON = 7
TEXT_HTML = 8
VIDEO_FLV = 9
APPLICATION_PDF = 10
APPLICATION_ZIP = 11
APPLICATION_HYDRUS_ENCRYPTED_ZIP = 12
AUDIO_MP3 = 13
VIDEO_MP4 = 14
AUDIO_OGG = 15
AUDIO_FLAC = 16
AUDIO_WMA = 17
VIDEO_WMV = 18
UNDETERMINED_WM = 19
VIDEO_MKV = 20
VIDEO_WEBM = 21
APPLICATION_JSON = 22
APPLICATION_OCTET_STREAM = 100
APPLICATION_UNKNOWN = 101

ALLOWED_MIMES = ( IMAGE_JPEG, IMAGE_PNG, IMAGE_GIF, IMAGE_BMP, APPLICATION_FLASH, VIDEO_FLV, VIDEO_MP4, VIDEO_MKV, VIDEO_WEBM, APPLICATION_PDF, AUDIO_MP3, AUDIO_OGG, AUDIO_FLAC, AUDIO_WMA, VIDEO_WMV )

IMAGES = ( IMAGE_JPEG, IMAGE_PNG, IMAGE_GIF, IMAGE_BMP )

AUDIO = ( AUDIO_MP3, AUDIO_OGG, AUDIO_FLAC, AUDIO_WMA )

VIDEO = ( VIDEO_FLV, VIDEO_MP4, VIDEO_WMV, VIDEO_MKV, VIDEO_WEBM )

NATIVE_VIDEO = ( VIDEO_MP4, VIDEO_WMV, VIDEO_MKV, VIDEO_WEBM )

APPLICATIONS = ( APPLICATION_FLASH, APPLICATION_PDF, APPLICATION_ZIP )

NOISY_MIMES = tuple( [ APPLICATION_FLASH ] + list( AUDIO ) + list( VIDEO ) )

ARCHIVES = ( APPLICATION_ZIP, APPLICATION_HYDRUS_ENCRYPTED_ZIP )

MIMES_WITH_THUMBNAILS = ( IMAGE_JPEG, IMAGE_PNG, IMAGE_GIF, IMAGE_BMP, VIDEO_WEBM, VIDEO_FLV, VIDEO_MP4, VIDEO_WMV, VIDEO_MKV, VIDEO_WEBM )

# mp3 header is complicated

mime_enum_lookup = {}

mime_enum_lookup[ 'collection' ] = APPLICATION_HYDRUS_CLIENT_COLLECTION
mime_enum_lookup[ 'image/jpe' ] = IMAGE_JPEG
mime_enum_lookup[ 'image/jpeg' ] = IMAGE_JPEG
mime_enum_lookup[ 'image/jpg' ] = IMAGE_JPEG
mime_enum_lookup[ 'image/x-png' ] = IMAGE_PNG
mime_enum_lookup[ 'image/png' ] = IMAGE_PNG
mime_enum_lookup[ 'image/gif' ] = IMAGE_GIF
mime_enum_lookup[ 'image/bmp' ] = IMAGE_BMP
mime_enum_lookup[ 'image' ] = IMAGES
mime_enum_lookup[ 'image/vnd.microsoft.icon' ] = IMAGE_ICON
mime_enum_lookup[ 'application/x-shockwave-flash' ] = APPLICATION_FLASH
mime_enum_lookup[ 'application/octet-stream' ] = APPLICATION_OCTET_STREAM
mime_enum_lookup[ 'application/x-yaml' ] = APPLICATION_YAML
mime_enum_lookup[ 'PDF document' ] = APPLICATION_PDF
mime_enum_lookup[ 'application/pdf' ] = APPLICATION_PDF
mime_enum_lookup[ 'application/zip' ] = APPLICATION_ZIP
mime_enum_lookup[ 'application/json' ] = APPLICATION_JSON
mime_enum_lookup[ 'application/hydrus-encrypted-zip' ] = APPLICATION_HYDRUS_ENCRYPTED_ZIP
mime_enum_lookup[ 'application' ] = APPLICATIONS
mime_enum_lookup[ 'audio/mp3' ] = AUDIO_MP3
mime_enum_lookup[ 'audio/ogg' ] = AUDIO_OGG
mime_enum_lookup[ 'audio/flac' ] = AUDIO_FLAC
mime_enum_lookup[ 'audio/x-ms-wma' ] = AUDIO_WMA
mime_enum_lookup[ 'text/html' ] = TEXT_HTML
mime_enum_lookup[ 'video/x-flv' ] = VIDEO_FLV
mime_enum_lookup[ 'video/mp4' ] = VIDEO_MP4
mime_enum_lookup[ 'video/x-ms-wmv' ] = VIDEO_WMV
mime_enum_lookup[ 'video/x-matroska' ] = VIDEO_MKV
mime_enum_lookup[ 'video/webm' ] = VIDEO_WEBM
mime_enum_lookup[ 'video' ] = VIDEO
mime_enum_lookup[ 'unknown mime' ] = APPLICATION_UNKNOWN

mime_string_lookup = {}

mime_string_lookup[ APPLICATION_HYDRUS_CLIENT_COLLECTION ] = 'collection'
mime_string_lookup[ IMAGE_JPEG ] = 'image/jpg'
mime_string_lookup[ IMAGE_PNG ] = 'image/png'
mime_string_lookup[ IMAGE_GIF ] = 'image/gif'
mime_string_lookup[ IMAGE_BMP ] = 'image/bmp'
mime_string_lookup[ IMAGES ] = 'image'
mime_string_lookup[ IMAGE_ICON ] = 'image/vnd.microsoft.icon'
mime_string_lookup[ APPLICATION_FLASH ] = 'application/x-shockwave-flash'
mime_string_lookup[ APPLICATION_OCTET_STREAM ] = 'application/octet-stream'
mime_string_lookup[ APPLICATION_YAML ] = 'application/x-yaml'
mime_string_lookup[ APPLICATION_JSON ] = 'application/json'
mime_string_lookup[ APPLICATION_PDF ] = 'application/pdf'
mime_string_lookup[ APPLICATION_ZIP ] = 'application/zip'
mime_string_lookup[ APPLICATION_HYDRUS_ENCRYPTED_ZIP ] = 'application/hydrus-encrypted-zip'
mime_string_lookup[ APPLICATIONS ] = 'application'
mime_string_lookup[ AUDIO_MP3 ] = 'audio/mp3'
mime_string_lookup[ AUDIO_OGG ] = 'audio/ogg'
mime_string_lookup[ AUDIO_FLAC ] = 'audio/flac'
mime_string_lookup[ AUDIO_WMA ] = 'audio/x-ms-wma'
mime_string_lookup[ AUDIO ] = 'audio'
mime_string_lookup[ TEXT_HTML ] = 'text/html'
mime_string_lookup[ VIDEO_FLV ] = 'video/x-flv'
mime_string_lookup[ VIDEO_MP4 ] = 'video/mp4'
mime_string_lookup[ VIDEO_WMV ] = 'video/x-ms-wmv'
mime_string_lookup[ VIDEO_MKV ] = 'video/x-matroska'
mime_string_lookup[ VIDEO_WEBM ] = 'video/webm'
mime_string_lookup[ VIDEO ] = 'video'
mime_string_lookup[ UNDETERMINED_WM ] = 'audio/x-ms-wma or video/x-ms-wmv'
mime_string_lookup[ APPLICATION_UNKNOWN ] = 'unknown mime'

mime_ext_lookup = {}

mime_ext_lookup[ APPLICATION_HYDRUS_CLIENT_COLLECTION ] = '.collection'
mime_ext_lookup[ IMAGE_JPEG ] = '.jpg'
mime_ext_lookup[ IMAGE_PNG ] = '.png'
mime_ext_lookup[ IMAGE_GIF ] = '.gif'
mime_ext_lookup[ IMAGE_BMP ] = '.bmp'
mime_ext_lookup[ IMAGE_ICON ] = '.ico'
mime_ext_lookup[ APPLICATION_FLASH ] = '.swf'
mime_ext_lookup[ APPLICATION_OCTET_STREAM ] = '.bin'
mime_ext_lookup[ APPLICATION_YAML ] = '.yaml'
mime_ext_lookup[ APPLICATION_JSON ] = '.json'
mime_ext_lookup[ APPLICATION_PDF ] = '.pdf'
mime_ext_lookup[ APPLICATION_ZIP ] = '.zip'
mime_ext_lookup[ APPLICATION_HYDRUS_ENCRYPTED_ZIP ] = '.zip.encrypted'
mime_ext_lookup[ AUDIO_MP3 ] = '.mp3'
mime_ext_lookup[ AUDIO_OGG ] = '.ogg'
mime_ext_lookup[ AUDIO_FLAC ] = '.flac'
mime_ext_lookup[ AUDIO_WMA ] = '.wma'
mime_ext_lookup[ TEXT_HTML ] = '.html'
mime_ext_lookup[ VIDEO_FLV ] = '.flv'
mime_ext_lookup[ VIDEO_MP4 ] = '.mp4'
mime_ext_lookup[ VIDEO_WMV ] = '.wmv'
mime_ext_lookup[ VIDEO_MKV ] = '.mkv'
mime_ext_lookup[ VIDEO_WEBM ] = '.webm'
mime_ext_lookup[ APPLICATION_UNKNOWN ] = ''
#mime_ext_lookup[ 'application/x-rar-compressed' ] = '.rar'

ALLOWED_MIME_EXTENSIONS = [ mime_ext_lookup[ mime ] for mime in ALLOWED_MIMES ]

PREDICATE_TYPE_SYSTEM = 0
PREDICATE_TYPE_TAG = 1
PREDICATE_TYPE_NAMESPACE = 2
PREDICATE_TYPE_PARENT = 3
PREDICATE_TYPE_WILDCARD = 4

SITE_TYPE_DEVIANT_ART = 0
SITE_TYPE_GIPHY = 1
SITE_TYPE_PIXIV = 2
SITE_TYPE_BOORU = 3
SITE_TYPE_TUMBLR = 4
SITE_TYPE_HENTAI_FOUNDRY = 5
SITE_TYPE_NEWGROUNDS = 6

site_type_string_lookup = {}

site_type_string_lookup[ SITE_TYPE_BOORU ] = 'booru'
site_type_string_lookup[ SITE_TYPE_DEVIANT_ART ] = 'deviant art'
site_type_string_lookup[ SITE_TYPE_GIPHY ] = 'giphy'
site_type_string_lookup[ SITE_TYPE_HENTAI_FOUNDRY ] = 'hentai foundry'
site_type_string_lookup[ SITE_TYPE_NEWGROUNDS ] = 'newgrounds'
site_type_string_lookup[ SITE_TYPE_PIXIV ] = 'pixiv'
site_type_string_lookup[ SITE_TYPE_TUMBLR ] = 'tumblr'

SYSTEM_PREDICATE_TYPE_EVERYTHING = 0
SYSTEM_PREDICATE_TYPE_INBOX = 1
SYSTEM_PREDICATE_TYPE_ARCHIVE = 2
SYSTEM_PREDICATE_TYPE_UNTAGGED = 3
SYSTEM_PREDICATE_TYPE_NUM_TAGS = 4
SYSTEM_PREDICATE_TYPE_LIMIT = 5
SYSTEM_PREDICATE_TYPE_SIZE = 6
SYSTEM_PREDICATE_TYPE_AGE = 7
SYSTEM_PREDICATE_TYPE_HASH = 8
SYSTEM_PREDICATE_TYPE_WIDTH = 9
SYSTEM_PREDICATE_TYPE_HEIGHT = 10
SYSTEM_PREDICATE_TYPE_RATIO = 11
SYSTEM_PREDICATE_TYPE_DURATION = 12
SYSTEM_PREDICATE_TYPE_MIME = 13
SYSTEM_PREDICATE_TYPE_RATING = 14
SYSTEM_PREDICATE_TYPE_SIMILAR_TO = 15
SYSTEM_PREDICATE_TYPE_LOCAL = 17
SYSTEM_PREDICATE_TYPE_NOT_LOCAL = 18
SYSTEM_PREDICATE_TYPE_NUM_WORDS = 19
SYSTEM_PREDICATE_TYPE_FILE_SERVICE = 20
SYSTEM_PREDICATE_TYPE_NUM_PIXELS = 21
SYSTEM_PREDICATE_TYPE_DIMENSIONS = 22

wxk_code_string_lookup = {
    wx.WXK_SPACE: 'space',
    wx.WXK_BACK: 'backspace',
    wx.WXK_TAB: 'tab',
    wx.WXK_RETURN: 'return',
    wx.WXK_NUMPAD_ENTER: 'enter',
    wx.WXK_PAUSE: 'pause',
    wx.WXK_ESCAPE: 'escape',
    wx.WXK_INSERT: 'insert',
    wx.WXK_DELETE: 'delete',
    wx.WXK_UP: 'up',
    wx.WXK_DOWN: 'down',
    wx.WXK_LEFT: 'left',
    wx.WXK_RIGHT: 'right',
    wx.WXK_HOME: 'home',
    wx.WXK_END: 'end',
    wx.WXK_PAGEDOWN: 'page up',
    wx.WXK_PAGEUP: 'page down',
    wx.WXK_F1: 'f1',
    wx.WXK_F2: 'f2',
    wx.WXK_F3: 'f3',
    wx.WXK_F4: 'f4',
    wx.WXK_F5: 'f5',
    wx.WXK_F6: 'f6',
    wx.WXK_F7: 'f7',
    wx.WXK_F8: 'f8',
    wx.WXK_F9: 'f9',
    wx.WXK_F10: 'f10',
    wx.WXK_F11: 'f11',
    wx.WXK_F12: 'f12',
    wx.WXK_ADD: '+',
    wx.WXK_DIVIDE: '/',
    wx.WXK_SUBTRACT: '-',
    wx.WXK_MULTIPLY: '*',
    wx.WXK_NUMPAD1: 'numpad 1',
    wx.WXK_NUMPAD2: 'numpad 2',
    wx.WXK_NUMPAD3: 'numpad 3',
    wx.WXK_NUMPAD4: 'numpad 4',
    wx.WXK_NUMPAD5: 'numpad 5',
    wx.WXK_NUMPAD6: 'numpad 6',
    wx.WXK_NUMPAD7: 'numpad 7',
    wx.WXK_NUMPAD8: 'numpad 8',
    wx.WXK_NUMPAD9: 'numpad 9',
    wx.WXK_NUMPAD0: 'numpad 0',
    wx.WXK_NUMPAD_UP: 'numpad up',
    wx.WXK_NUMPAD_DOWN: 'numpad down',
    wx.WXK_NUMPAD_LEFT: 'numpad left',
    wx.WXK_NUMPAD_RIGHT: 'numpad right',
    wx.WXK_NUMPAD_HOME: 'numpad home',
    wx.WXK_NUMPAD_END: 'numpad end',
    wx.WXK_NUMPAD_PAGEDOWN: 'numpad page up',
    wx.WXK_NUMPAD_PAGEUP: 'numpad page down',
    wx.WXK_NUMPAD_ADD: 'numpad +',
    wx.WXK_NUMPAD_DIVIDE: 'numpad /',
    wx.WXK_NUMPAD_SUBTRACT: 'numpad -',
    wx.WXK_NUMPAD_MULTIPLY: 'numpad *',
    wx.WXK_NUMPAD_DELETE: 'numpad delete',
    wx.WXK_NUMPAD_DECIMAL: 'numpad decimal'
    }

# request checking

BANDWIDTH_CONSUMING_REQUESTS = set()

BANDWIDTH_CONSUMING_REQUESTS.add( ( LOCAL_BOORU, GET, 'gallery' ) )
BANDWIDTH_CONSUMING_REQUESTS.add( ( LOCAL_BOORU, GET, 'page' ) )
BANDWIDTH_CONSUMING_REQUESTS.add( ( LOCAL_BOORU, GET, 'file' ) )
BANDWIDTH_CONSUMING_REQUESTS.add( ( LOCAL_BOORU, GET, 'thumbnail' ) )
BANDWIDTH_CONSUMING_REQUESTS.add( ( TAG_REPOSITORY, GET, 'content_update_package' ) )
BANDWIDTH_CONSUMING_REQUESTS.add( ( TAG_REPOSITORY, GET, 'service_update_package' ) )
BANDWIDTH_CONSUMING_REQUESTS.add( ( TAG_REPOSITORY, POST, 'content_update_package' ) )
BANDWIDTH_CONSUMING_REQUESTS.add( ( FILE_REPOSITORY, GET, 'content_update_package' ) )
BANDWIDTH_CONSUMING_REQUESTS.add( ( FILE_REPOSITORY, GET, 'file' ) )
BANDWIDTH_CONSUMING_REQUESTS.add( ( FILE_REPOSITORY, GET, 'service_update_package' ) )
BANDWIDTH_CONSUMING_REQUESTS.add( ( FILE_REPOSITORY, GET, 'thumbnail' ) )
BANDWIDTH_CONSUMING_REQUESTS.add( ( FILE_REPOSITORY, POST, 'content_update_package' ) )
BANDWIDTH_CONSUMING_REQUESTS.add( ( FILE_REPOSITORY, POST, 'file' ) )

# default options

DEFAULT_LOCAL_FILE_PORT = 45865
DEFAULT_LOCAL_BOORU_PORT = 45866
DEFAULT_SERVER_ADMIN_PORT = 45870
DEFAULT_SERVICE_PORT = 45871

DEFAULT_OPTIONS = {}

DEFAULT_OPTIONS[ SERVER_ADMIN ] = {}
DEFAULT_OPTIONS[ SERVER_ADMIN ][ 'max_monthly_data' ] = None
DEFAULT_OPTIONS[ SERVER_ADMIN ][ 'max_storage' ] = None
DEFAULT_OPTIONS[ SERVER_ADMIN ][ 'message' ] = 'hydrus server administration service'
DEFAULT_OPTIONS[ SERVER_ADMIN ][ 'upnp' ] = None

DEFAULT_OPTIONS[ FILE_REPOSITORY ] = {}
DEFAULT_OPTIONS[ FILE_REPOSITORY ][ 'max_monthly_data' ] = None
DEFAULT_OPTIONS[ FILE_REPOSITORY ][ 'max_storage' ] = None
DEFAULT_OPTIONS[ FILE_REPOSITORY ][ 'log_uploader_ips' ] = False
DEFAULT_OPTIONS[ FILE_REPOSITORY ][ 'message' ] = 'hydrus file repository'
DEFAULT_OPTIONS[ FILE_REPOSITORY ][ 'upnp' ] = None

DEFAULT_OPTIONS[ TAG_REPOSITORY ] = {}
DEFAULT_OPTIONS[ TAG_REPOSITORY ][ 'max_monthly_data' ] = None
DEFAULT_OPTIONS[ TAG_REPOSITORY ][ 'message' ] = 'hydrus tag repository'
DEFAULT_OPTIONS[ TAG_REPOSITORY ][ 'upnp' ] = None

DEFAULT_OPTIONS[ MESSAGE_DEPOT ] = {}
DEFAULT_OPTIONS[ MESSAGE_DEPOT ][ 'max_monthly_data' ] = None
DEFAULT_OPTIONS[ MESSAGE_DEPOT ][ 'max_storage' ] = None
DEFAULT_OPTIONS[ MESSAGE_DEPOT ][ 'message' ] = 'hydrus message depot'
DEFAULT_OPTIONS[ MESSAGE_DEPOT ][ 'upnp' ] = None

# Hydrus pubsub

SERVER_ADMIN_KEY = 'server admin'

def construct_python_tuple( self, node ): return tuple( self.construct_sequence( node ) )
def represent_python_tuple( self, data ): return self.represent_sequence( u'tag:yaml.org,2002:python/tuple', data )

yaml.SafeLoader.add_constructor( u'tag:yaml.org,2002:python/tuple', construct_python_tuple )
yaml.SafeDumper.add_representer( tuple, represent_python_tuple )

# for some reason, sqlite doesn't parse to int before this, despite the column affinity
# it gives the register_converter function a bytestring :/
def integer_boolean_to_bool( integer_boolean ): return bool( int( integer_boolean ) )

# sqlite mod

sqlite3.register_adapter( dict, yaml.safe_dump )
sqlite3.register_adapter( list, yaml.safe_dump )
sqlite3.register_adapter( tuple, yaml.safe_dump )
sqlite3.register_adapter( bool, int )

sqlite3.register_converter( 'BLOB_BYTES', str )
sqlite3.register_converter( 'INTEGER_BOOLEAN', integer_boolean_to_bool )
sqlite3.register_converter( 'TEXT_YAML', yaml.safe_load )