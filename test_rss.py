# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from sopel.db import SopelDB
from sopel.formatting import bold
from sopel.modules import rss
from sopel.test_tools import MockSopel, MockConfig
import feedparser
import hashlib
import os
import pytest
import tempfile
import types


FEED_VALID = '''<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0" xml:base="http://www.site1.com/feed" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Site 1 Articles</title>
<link>http://www.site1.com/feed</link>
<description></description>
<language>en</language>

<item>
<title>Title 3</title>
<link>http://www.site1.com/article3</link>
<description>&lt;p&gt;Description of article 3&lt;/p&gt;</description>
<summary>&lt;p&gt;Summary of article 3&lt;/p&gt;</summary>
<author>Author 3</author>
<pubDate>Sat, 23 Aug 2016 03:30:33 +0000</pubDate>
<guid isPermaLink="false">3 at http://www.site1.com/</guid>
</item>

<item>
<title>Title 2</title>
<link>http://www.site1.com/article2</link>
<description>&lt;p&gt;Description of article 2&lt;/p&gt;</description>
<summary>&lt;p&gt;Summary of article 2&lt;/p&gt;</summary>
<author>Author 2</author>
<pubDate>Sat, 22 Aug 2016 02:20:22 +0000</pubDate>
<guid isPermaLink="false">2 at http://www.site1.com/</guid>
</item>

<item>
<title>Title 1</title>
<link>http://www.site1.com/article1</link>
<description>&lt;p&gt;Description of article 1&lt;/p&gt;</description>
<summary>&lt;p&gt;Summary of article 1&lt;/p&gt;</summary>
<author>Author 1</author>
<pubDate>Sat, 21 Aug 2016 01:10:11 +0000</pubDate>
<guid isPermaLink="false">1 at http://www.site1.com/</guid>
</item>

</channel>
</rss>'''


FEED_BASIC = '''<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0" xml:base="http://www.site1.com/feed" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Site 1 Articles</title>
<link>http://www.site1.com/feed</link>

<item>
<title>Title 3</title>
<link>http://www.site1.com/article3</link>
</item>

<item>
<title>Title 2</title>
<link>http://www.site1.com/article2</link>
</item>

<item>
<title>Title 1</title>
<link>http://www.site1.com/article1</link>
</item>

</channel>
</rss>'''


FEED_INVALID = '''<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0" xml:base="http://www.site1.com/feed" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Site 1 Articles</title>
<link>http://www.site1.com/feed</link>
<description></description>
<language>en</language>
</channel>
</rss>'''


FEED_ITEM_NEITHER_TITLE_NOR_DESCRIPTION = '''<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0" xml:base="http://www.site1.com/feed" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Site</title>
<link>http://www.site.com/feed</link>
<description></description>

<item>
<link>http://www.site.com/article</link>
</item>

</channel>
</rss>'''


def _fixture_bot_setup(request):
    bot = MockSopel('Sopel')
    bot = rss._config_define(bot)
    bot.config.core.db_filename = tempfile.mkstemp()[1]
    bot.db = SopelDB(bot.config)
    bot.output = ''

    # monkey patch bot
    def join(self, channel):
        if channel not in bot.channels:
            bot.config.core.channels.append(channel)
    bot.join = types.MethodType(join, bot)
    def say(self, message, channel = ''):
        bot.output += message + "\n"
    bot.say = types.MethodType(say, bot)

    # tear down bot
    def fin():
        os.remove(bot.config.filename)
        os.remove(bot.config.core.db_filename)
    request.addfinalizer(fin)

    return bot


def _fixture_bot_add_data(bot, id, url):
    bot.memory['rss']['feeds']['feed'+id] = {'channel': '#channel' + id, 'name': 'feed' + id, 'url': url}
    bot.memory['rss']['hashes']['feed'+id] = rss.RingBuffer(100)
    feedreader = MockFeedReader(FEED_VALID)
    bot.memory['rss']['formats']['feeds']['feed'+id] = rss.FeedFormater(bot, feedreader)
    sql_create_table = 'CREATE TABLE ' + rss._digest_tablename('feed'+id) + ' (id INTEGER PRIMARY KEY, hash VARCHAR(32) UNIQUE)'
    bot.db.execute(sql_create_table)
    bot.config.core.channels = ['#channel' + id]
    return bot


@pytest.fixture(scope="function")
def bot(request):
    bot = _fixture_bot_setup(request)
    bot = _fixture_bot_add_data(bot, '1', 'http://www.site1.com/feed')
    return bot


@pytest.fixture(scope="function")
def bot_config_save(request):
    bot = _fixture_bot_setup(request)
    bot = _fixture_bot_add_data(bot, '1', 'http://www.site1.com/feed')
    return bot


@pytest.fixture(scope="function")
def bot_basic(request):
    bot = _fixture_bot_setup(request)
    return bot


@pytest.fixture(scope="function")
def bot_rss_list(request):
    bot = _fixture_bot_setup(request)
    bot = _fixture_bot_add_data(bot, '1', 'http://www.site1.com/feed')
    bot = _fixture_bot_add_data(bot, '2', 'http://www.site2.com/feed')
    return bot


@pytest.fixture(scope="function")
def bot_rss_update(request):
    bot = _fixture_bot_setup(request)
    bot = _fixture_bot_add_data(bot, '1', FEED_VALID)
    return bot


@pytest.fixture(scope="module")
def feedreader_feed_valid():
    return MockFeedReader(FEED_VALID)


@pytest.fixture(scope="module")
def feedreader_feed_invalid():
    return MockFeedReader(FEED_INVALID)


@pytest.fixture(scope="module")
def feedreader_feed_item_neither_title_nor_description():
    return MockFeedReader(FEED_ITEM_NEITHER_TITLE_NOR_DESCRIPTION)


# Implementing a mock rss feed get_feeder
class MockFeedReader:
    def __init__(self, url):
        self.url = url

    def get_feed(self):
        feed = feedparser.parse(self.url)
        return feed

    def get_tinyurl(self, url):
        return 'https://tinyurl.com/govvpmm'


def test_rss_global_too_many_parameters(bot):
    rss._rss(bot, ['add', '#channel', 'feedname', FEED_VALID, 'fl+ftl', 'fifth_argument'])
    expected = rss.COMMANDS['add']['synopsis'].format(bot.config.core.prefix) + '\n'
    assert expected == bot.output


def test_rss_global_too_few_parameters(bot):
    rss._rss(bot, ['add', '#channel', 'feedname'])
    expected = rss.COMMANDS['add']['synopsis'].format(bot.config.core.prefix) + '\n'
    assert expected == bot.output


def test_rss_global_config_templates(bot):
    rss._rss(bot, ['config', 'templates'])
    expected = 'a|<{}>,d|{},f|' + bold('[{}]') + ',g|{},l|' + bold('→') + ' {}'
    expected += ',p|({}),s|{},t|{},y|' + bold('→') + ' {}\n'
    assert expected == bot.output


def test_rss_global_feed_add(bot):
    rss._rss(bot, ['add', '#channel', 'feedname', FEED_VALID])
    assert rss._feed_exists(bot, 'feedname') == True


def test_rss_global_feed_delete(bot):
    rss._rss(bot, ['add', '#channel', 'feedname', FEED_VALID])
    rss._rss(bot, ['del', 'feedname'])
    assert rss._feed_exists(bot, 'feedname') == False


def test_rss_global_fields_get(bot):
    rss._rss(bot, ['fields', 'feed1'])
    expected = rss.MESSAGES['fields_of_feed_are'].format('feed1', 'fadglpsty') + '\n'
    assert expected == bot.output


def test_rss_global_format_set(bot):
    rss._rss(bot, ['format', 'feed1', 'asl+als'])
    format_new = bot.memory['rss']['formats']['feeds']['feed1'].get_format()
    assert 'asl+als' == format_new


def test_rss_global_format_feed(bot):
    rss._rss(bot, ['format', 'feed1', 'apl+atl'])
    bot.output = ''
    args = ['config', 'feeds']
    rss._rss_config(bot, args)
    expected = '#channel1|feed1|http://www.site1.com/feed|apl+atl\n'
    assert expected == bot.output


def test_rss_global_get_post_feed_items(bot):
    rss._rss(bot, ['add', '#channel', 'feedname', FEED_VALID])
    bot.output = ''
    rss._rss(bot, ['get', 'feedname'])
    expected = bold('[feedname]') + ' Title 1 ' + bold('→') + " http://www.site1.com/article1\n" + bold('[feedname]') + ' Title 2 ' + bold('→') + " http://www.site1.com/article2\n" + bold('[feedname]') + ' Title 3 ' + bold('→') + " http://www.site1.com/article3\n"
    assert expected == bot.output


def test_rss_global_help_synopsis_help(bot):
    rss._rss(bot, ['help'])
    expected = rss.COMMANDS['help']['synopsis'].format(bot.config.core.prefix) + '\n'
    expected += rss.MESSAGES['command_is_one_of'].format('|'.join(sorted(rss.COMMANDS.keys()))) + '\n'
    assert expected == bot.output


def test_rss_global_join(bot):
    rss._rss(bot, ['join'])
    channels = []
    for feed in bot.memory['rss']['feeds']:
        feedchannel = bot.memory['rss']['feeds'][feed]['channel']
        if feedchannel not in channels:
            channels.append(feedchannel)
    assert channels == bot.config.core.channels


def test_rss_global_list_feed(bot):
    rss._rss(bot, ['list', 'feed1'])
    expected = '#channel1 feed1 http://www.site1.com/feed fl+ftl\n'
    assert expected == bot.output


def test_rss_global_update_update(bot_rss_update):
    rss._rss(bot_rss_update, ['update'])
    expected = bold('[feed1]') + ' Title 1 ' + bold('→') + " http://www.site1.com/article1\n" + bold('[feed1]') + ' Title 2 ' + bold('→') + " http://www.site1.com/article2\n" + bold('[feed1]') + ' Title 3 ' + bold('→') + " http://www.site1.com/article3\n"
    assert expected == bot_rss_update.output


def test_rss_add_feed_add(bot):
    rss._rss_add(bot, ['add', '#channel', 'feedname', FEED_VALID])
    assert rss._feed_exists(bot, 'feedname') == True


def test_rss_config_feeds_list(bot):
    rss._rss_format(bot, ['format', 'feed1', 'asl+als'])
    rss._rss_add(bot, ['add', '#channel2', 'feed2', FEED_VALID, 'p+tlpas'])
    bot.output = ''
    args = ['config', 'feeds']
    rss._rss_config(bot, args)
    expected = '#channel1|feed1|http://www.site1.com/feed|asl+als,#channel2|feed2|' + FEED_VALID + '|p+tlpas\n'
    assert expected == bot.output


def test_rss_config_formats_list(bot):
    bot.memory['rss']['formats']['default'] = ['lts+flts','at+at']
    args = ['config', 'formats']
    rss._rss_config(bot, args)
    expected = 'lts+flts,at+at,fl+ftl' + '\n'
    assert expected == bot.output


def test_rss_config_templates_list(bot):
    bot.memory['rss']['templates']['default']['t'] = '†{}†'
    args = ['config', 'templates']
    rss._rss_config(bot, args)
    expected = 'a|<{}>,d|{},f|\x02[{}]\x02,g|{},l|\x02→\x02 {},p|({}),s|{},t|†{}†,y|\x02→\x02 {}' + '\n'
    assert expected == bot.output


def test_rss_config_invalid_key(bot):
    rss._rss_config(bot, ['config', 'invalidkey'])
    expected = ''
    assert expected == bot.output


def test_rss_del_feed_nonexistent(bot):
    rss._rss_del(bot, ['del', 'abcd'])
    expected = rss.MESSAGES['feed_does_not_exist'].format('abcd') + '\n'
    assert expected == bot.output


def test_rss_del_feed_delete(bot):
    rss._rss_add(bot, ['add', '#channel', 'feedname', FEED_VALID])
    rss._rss_del(bot, ['del', 'feedname'])
    assert rss._feed_exists(bot, 'feedname') == False


def test_rss_fields_feed_nonexistent(bot):
    rss._rss_fields(bot, ['fields', 'abcd'])
    expected = rss.MESSAGES['feed_does_not_exist'].format('abcd') + '\n'
    assert expected == bot.output


def test_rss_fields_get_default(bot):
    rss._rss_fields(bot, ['fields', 'feed1'])
    expected = rss.MESSAGES['fields_of_feed_are'].format('feed1', 'fadglpsty') + '\n'
    assert expected == bot.output


def test_rss_fields_get_custom(bot):
    rss._rss_add(bot, ['add', '#channel', 'feedname', FEED_VALID, 'fltp+atl'])
    bot.output = ''
    rss._rss_fields(bot, ['fields', 'feedname'])
    expected = rss.MESSAGES['fields_of_feed_are'].format('feedname', 'fadglpsty') + '\n'
    assert expected == bot.output


def test_rss_format_feed_nonexistent(bot):
    rss._rss_format(bot, ['format', 'abcd', ''])
    expected = rss.MESSAGES['feed_does_not_exist'].format('abcd') + '\n'
    assert expected == bot.output


def test_rss_format_format_unchanged(bot):
    format_old = bot.memory['rss']['formats']['feeds']['feed1'].get_format()
    rss._rss_format(bot, ['format', 'feed1', 'abcd+efgh'])
    format_new = bot.memory['rss']['formats']['feeds']['feed1'].get_format()
    assert format_old == format_new
    expected = rss.MESSAGES['consider_rss_fields'].format(bot.config.core.prefix, 'feed1') + '\n'
    assert expected == bot.output


def test_rss_format_format_changed(bot):
    format_old = bot.memory['rss']['formats']['feeds']['feed1'].get_format()
    rss._rss_format(bot, ['format', 'feed1', 'asl+als'])
    format_new = bot.memory['rss']['formats']['feeds']['feed1'].get_format()
    assert format_old != format_new


def test_rss_format_format_set(bot):
    rss._rss_format(bot, ['format', 'feed1', 'asl+als'])
    format_new = bot.memory['rss']['formats']['feeds']['feed1'].get_format()
    assert 'asl+als' == format_new


def test_rss_format_format_output(bot_rss_update):
    rss._rss_format(bot_rss_update, ['format', 'feed1', 'fadglpst+fadglpst'])
    rss._rss_update(bot_rss_update, ['update'])
    expected = rss.MESSAGES['format_of_feed_has_been_set_to'].format('feed1', 'fadglpst+fadglpst') + '''
\x02[feed1]\x02 <Author 1> <p>Description of article 1</p> 1 at http://www.site1.com/ \x02→\x02 http://www.site1.com/article1 (2016-08-21 01:10) <p>Description of article 1</p> Title 1
\x02[feed1]\x02 <Author 2> <p>Description of article 2</p> 2 at http://www.site1.com/ \x02→\x02 http://www.site1.com/article2 (2016-08-22 02:20) <p>Description of article 2</p> Title 2
\x02[feed1]\x02 <Author 3> <p>Description of article 3</p> 3 at http://www.site1.com/ \x02→\x02 http://www.site1.com/article3 (2016-08-23 03:30) <p>Description of article 3</p> Title 3
'''
    assert expected == bot_rss_update.output


def test_rss_get_feed_nonexistent(bot):
    rss._rss_get(bot, ['get', 'abcd'])
    expected = rss.MESSAGES['feed_does_not_exist'].format('abcd') + '\n'
    assert expected == bot.output


def test_rss_get_post_feed_items(bot):
    rss._feed_add(bot, '#channel', 'feedname', FEED_VALID)
    rss._rss_get(bot, ['get', 'feedname'])
    expected = bold('[feedname]') + ' Title 1 ' + bold('→') + " http://www.site1.com/article1\n" + bold('[feedname]') + ' Title 2 ' + bold('→') + " http://www.site1.com/article2\n" + bold('[feedname]') + ' Title 3 ' + bold('→') + " http://www.site1.com/article3\n"
    assert expected == bot.output


def test_rss_help_synopsis_help(bot):
    rss._rss_help(bot, ['help'])
    expected = rss.COMMANDS['help']['synopsis'].format(bot.config.core.prefix) + '\n'
    expected += rss.MESSAGES['command_is_one_of'].format('|'.join(sorted(rss.COMMANDS.keys()))) + '\n'
    assert expected == bot.output


def test_rss_help_add(bot):
    rss._rss_help(bot, ['help', 'add'])
    expected = rss.COMMANDS['add']['synopsis'].format(bot.config.core.prefix) + '\n'
    for message in rss.COMMANDS['add']['helptext']:
        expected += message + '\n'
    expected += rss.MESSAGES['examples'] + '\n'
    for message in rss.COMMANDS['add']['examples']:
        expected += message.format(bot.config.core.prefix) + '\n'
    assert expected == bot.output


def test_rss_help_config(bot):
    rss._rss_help(bot, ['help', 'config'])
    expected = rss.COMMANDS['config']['synopsis'].format(bot.config.core.prefix) + '\n'
    for message in rss.COMMANDS['config']['helptext']:
        expected += message + '\n'
    expected += rss.MESSAGES['examples'] + '\n'
    for message in rss.COMMANDS['config']['examples']:
        expected += message.format(bot.config.core.prefix) + '\n'
    expected += rss.MESSAGES['get_help_on_config_keys_with'].format(bot.config.core.prefix, '|'.join(sorted(rss.CONFIG.keys()))) + '\n'
    assert expected == bot.output


def test_rss_help_config_templates(bot):
    rss._rss_help(bot, ['help', 'config', 'templates'])
    expected = rss.CONFIG['templates']['synopsis'].format(bot.config.core.prefix) + '\n'
    for message in rss.CONFIG['templates']['helptext']:
        expected += message + '\n'
    expected += rss.MESSAGES['examples'] + '\n'
    for message in rss.CONFIG['templates']['examples']:
        expected += message.format(bot.config.core.prefix) + '\n'
    assert expected == bot.output


def test_rss_join(bot):
    rss._rss_join(bot, ['join'])
    channels = []
    for feed in bot.memory['rss']['feeds']:
        feedchannel = bot.memory['rss']['feeds'][feed]['channel']
        if feedchannel not in channels:
            channels.append(feedchannel)
    assert channels == bot.config.core.channels


def test_rss_list_all(bot_rss_list):
    rss._rss_list(bot_rss_list, ['list'])
    expected1 = '#channel1 feed1 http://www.site1.com/feed'
    expected2 = '#channel2 feed2 http://www.site2.com/feed'
    assert expected1 in bot_rss_list.output
    assert expected2 in bot_rss_list.output


def test_rss_list_feed(bot):
    rss._rss_list(bot, ['list', 'feed1'])
    expected = '#channel1 feed1 http://www.site1.com/feed fl+ftl\n'
    assert expected == bot.output


def test_rss_list_channel(bot):
    rss._rss_list(bot, ['list', '#channel1'])
    expected = '#channel1 feed1 http://www.site1.com/feed fl+ftl\n'
    assert expected == bot.output


def test_rss_list_no_feed_found(bot):
    rss._rss_list(bot, ['lsit', 'invalid'])
    assert '' == bot.output


def test_rss_update_update(bot_rss_update):
    rss._rss_update(bot_rss_update, ['update'])
    expected = bold('[feed1]') + ' Title 1 ' + bold('→') + " http://www.site1.com/article1\n" + bold('[feed1]') + ' Title 2 ' + bold('→') + " http://www.site1.com/article2\n" + bold('[feed1]') + ' Title 3 ' + bold('→') + " http://www.site1.com/article3\n"
    assert expected == bot_rss_update.output


def test_rss_update_no_update(bot_rss_update):
    rss._rss_update(bot_rss_update, ['update'])
    bot.output = ''
    rss._rss_update(bot_rss_update, ['update'])
    assert '' == bot.output


def test_config_define_sopelmemory():
    bot = MockSopel('Sopel')
    bot = rss._config_define(bot)
    assert type(bot.memory['rss']) == rss.SopelMemory


def test_config_define_feeds():
    bot = MockSopel('Sopel')
    bot = rss._config_define(bot)
    assert type(bot.memory['rss']['feeds']) == dict


def test_config_define_hashes():
    bot = MockSopel('Sopel')
    bot = rss._config_define(bot)
    assert type(bot.memory['rss']['hashes']) == dict


def test_config_define_formats():
    bot = MockSopel('Sopel')
    bot = rss._config_define(bot)
    assert type(bot.memory['rss']['formats']['feeds']) == dict


def test_config_concatenate_channels(bot):
    channels = rss._config_concatenate_channels(bot)
    expected = ['#channel1']
    assert expected == channels


def test_config_concatenate_feeds(bot, feedreader_feed_valid):
    bot.memory['rss']['formats']['feeds']['feed1'] = rss.FeedFormater(bot, feedreader_feed_valid, 'fy+fty')
    feeds = rss._config_concatenate_feeds(bot)
    expected = ['#channel1|feed1|http://www.site1.com/feed|fy+fty']
    assert expected == feeds


def test_config_concatenate_formats(bot):
    bot.memory['rss']['formats']['default'] = ['yt+yt','ftla+ft']
    formats = rss._config_concatenate_formats(bot)
    expected = ['yt+yt,ftla+ft']
    assert expected == formats


def test_config_concatenate_templates(bot):
    bot.memory['rss']['templates']['default']['t'] = '<>t<>'
    templates = rss._config_concatenate_templates(bot)
    expected = ['t|<>t<>']
    assert expected == templates


def test_config_read_feed_default(bot_basic):
    rss._config_read(bot_basic)
    feeds = bot_basic.memory['rss']['feeds']
    expected = {}
    assert expected == feeds


def test_config_read_format_default(bot_basic):
    bot_basic.config.rss.formats = [rss.FORMAT_DEFAULT]
    rss._config_read(bot_basic)
    formats = bot_basic.memory['rss']['formats']['default']
    expected = [rss.FORMAT_DEFAULT]
    assert expected == formats


def test_config_read_format_custom_valid(bot_basic):
    formats_custom = ['al+fpatl','y+fty']
    bot_basic.config.rss.formats = formats_custom
    rss._config_read(bot_basic)
    formats = bot_basic.memory['rss']['formats']['default']
    assert formats_custom == formats


def test_config_read_format_custom_invalid(bot_basic):
    formats_custom = ['al+fpatl','yy+fty']
    bot_basic.config.rss.formats = formats_custom
    rss._config_read(bot_basic)
    formats = bot_basic.memory['rss']['formats']['default']
    expected = ['al+fpatl']
    assert expected == formats


def test_config_read_template_default(bot_basic):
    for t in rss.TEMPLATES_DEFAULT:
        bot_basic.config.rss.templates.append(t + '|' + rss.TEMPLATES_DEFAULT[t])
    rss._config_read(bot_basic)
    templates = bot_basic.memory['rss']['templates']['default']
    expected = rss.TEMPLATES_DEFAULT
    assert expected == templates


def test_config_read_template_custom(bot_basic):
    templates_custom = ['t|>>{}<<']
    bot_basic.config.rss.templates = templates_custom
    rss._config_read(bot_basic)
    templates = bot_basic.memory['rss']['templates']['default']
    expected = dict()
    for t in rss.TEMPLATES_DEFAULT:
        expected[t] = rss.TEMPLATES_DEFAULT[t]
    expected['t'] = '>>{}<<'
    assert expected == templates


def test_config_save_writes(bot_config_save):
    bot_config_save.memory['rss']['formats']['default'] = ['ft+ftpal']
    for t in rss.TEMPLATES_DEFAULT:
        bot_config_save.memory['rss']['templates']['default'][t] = rss.TEMPLATES_DEFAULT[t]
    bot_config_save.memory['rss']['templates']['default']['a'] = '<{}>'
    bot_config_save.memory['rss']['templates']['default']['t'] = '<<{}>>'
    rss._config_save(bot_config_save)
    expected = '''[core]
owner = '''+'''
admins = '''+'''
homedir = ''' + bot_config_save.config.homedir + '''
db_filename = ''' + bot_config_save.db.filename + '''
channels = #channel1

[rss]
feeds = #channel1|feed1|http://www.site1.com/feed|fl+ftl
formats = ft+ftpal
templates = t|<<{}>>

'''
    f = open(bot_config_save.config.filename, 'r')
    config = f.read()
    assert expected == config


def test_config_set_feeds_get(bot_basic):
    feeds = '#channelA|feedA|' + FEED_BASIC + '|t+t,#channelB|feedB|' + FEED_BASIC + '|tl+tl'
    rss._config_set_feeds(bot_basic, feeds)
    get = rss._config_get_feeds(bot_basic)
    assert feeds == get


def test_config_set_feeds_exists(bot_basic):
    feeds = '#channelA|feedA|' + FEED_BASIC + '|fyg+fgty,#channelB|feedB|' + FEED_BASIC + '|lp+fptl'
    rss._config_set_feeds(bot_basic, feeds)
    result = rss._feed_exists(bot_basic, 'feedB')
    assert True == result


def test_config_set_formats_get(bot):
    formats = 't+t,d+d'
    rss._config_set_formats(bot, formats)
    get = rss._config_get_formats(bot)
    expected = formats + ',' + rss.FORMAT_DEFAULT
    assert expected == get


def test_config_set_formats_join(bot):
    formats = 't+t,d+d'
    rss._config_set_formats(bot, formats)
    formats_bot = ','.join(bot.memory['rss']['formats']['default'])
    assert formats == formats_bot


def test_config_set_templates_get(bot):
    templates = 't|≈{}≈,s|√{}'
    rss._config_set_templates(bot, templates)
    get = rss._config_get_templates(bot)
    expected_dict = dict()
    for f in rss.TEMPLATES_DEFAULT:
        expected_dict[f] = rss.TEMPLATES_DEFAULT[f]
    expected_dict['s'] = '√{}'
    expected_dict['t'] = '≈{}≈'
    expected_list = list()
    for f in expected_dict:
        expected_list.append(f + '|' + expected_dict[f])
    expected = ','.join(sorted(expected_list))
    assert expected == get


def test_config_set_templates_dict(bot):
    templates = 't|≈{}≈,s|√{}'
    rss._config_set_templates(bot, templates)
    template = bot.memory['rss']['templates']['default']['s']
    assert '√{}' == template


def test_config_split_feeds_valid(bot):
    feeds = ['#channel2|feed2|' + FEED_VALID + '|fy+fty']
    rss._config_split_feeds(bot, feeds)
    assert rss._feed_exists(bot, 'feed2')


def test_config_split_feeds_invalid(bot):
    feeds = ['#channel2|feed2|' + FEED_ITEM_NEITHER_TITLE_NOR_DESCRIPTION + '|fy+fty']
    rss._config_split_feeds(bot, feeds)
    assert not rss._feed_exists(bot, 'feed2')


def test_config_split_formats_valid(bot):
    formats = ['yt+yt','ftla+ft']
    formats_split = rss._config_split_formats(bot, formats)
    expected = ['yt+yt', 'ftla+ft']
    assert expected == formats_split


def test_config_split_formats_invalid(bot):
    formats = ['abcd','ftla+ft']
    formats_split = rss._config_split_formats(bot, formats)
    expected = ['ftla+ft']
    assert expected == formats_split


def test_config_split_templates_valid(bot):
    templates = { 't|>>{}<<' }
    templates_split = rss._config_split_templates(bot, templates)
    assert templates_split['t'] == '>>{}<<'


def test_config_split_templates_invalid(bot):
    templates = { 't|>><<' }
    templates_split = rss._config_split_templates(bot, templates)
    assert templates_split['t'] == '{}'


def test_db_create_table_and_db_check_if_table_exists(bot):
    rss._db_create_table(bot, 'feedname')
    result = rss._db_check_if_table_exists(bot, 'feedname')
    assert [(rss._digest_tablename('feedname'),)] == result


def test_db_drop_table(bot):
    rss._db_create_table(bot, 'feedname')
    rss._db_drop_table(bot, 'feedname')
    result = rss._db_check_if_table_exists(bot, 'feedname')
    assert [] == result


def test_db_get_numer_of_rows(bot):
    ROWS = 10
    for i in range(ROWS):
        hash = rss.hashlib.md5(str(i).encode('utf-8')).hexdigest()
        bot.memory['rss']['hashes']['feed1'].append(hash)
        rss._db_save_hash_to_database(bot, 'feed1', hash)
    rows_feed = rss._db_get_number_of_rows(bot, 'feed1')
    assert ROWS == rows_feed


def test_db_remove_old_hashes_from_database(bot):
    SURPLUS_ROWS = 10
    bot.memory['rss']['hashes']['feed1'] = rss.RingBuffer(rss.MAX_HASHES_PER_FEED + SURPLUS_ROWS)
    for i in range(rss.MAX_HASHES_PER_FEED + SURPLUS_ROWS):
        hash = hashlib.md5(str(i).encode('utf-8')).hexdigest()
        bot.memory['rss']['hashes']['feed1'].append(hash)
        rss._db_save_hash_to_database(bot, 'feed1', hash)
    rss._db_remove_old_hashes_from_database(bot, 'feed1')
    rows_feed = rss._db_get_number_of_rows(bot, 'feed1')
    assert rss.MAX_HASHES_PER_FEED == rows_feed


def test_db_save_hash_to_database(bot):
    rss._db_save_hash_to_database(bot, 'feed1', '463f9357db6c20a94a68f9c9ef3bb0fb')
    hashes = rss._db_read_hashes_from_database(bot, 'feed1')
    expected = [(1, '463f9357db6c20a94a68f9c9ef3bb0fb')]
    assert expected == hashes


def test_digest_tablename_works():
    digest = rss._digest_tablename('thisisatest')
    assert 'rss_f830f69d23b8224b512a0dc2f5aec974' == digest


def test_feed_add_create_db_table(bot):
    rss._feed_add(bot, '#channel', 'feedname', FEED_VALID)
    result = rss._db_check_if_table_exists(bot, 'feedname')
    assert [(rss._digest_tablename('feedname'),)] == result


def test_feed_add_create_ring_buffer(bot):
    rss._feed_add(bot, '#channel', 'feedname', FEED_VALID)
    assert type(bot.memory['rss']['hashes']['feedname']) == rss.RingBuffer


def test_feed_add_create_feed(bot):
    rss._feed_add(bot, '#channel', 'feedname', FEED_VALID)
    feed = bot.memory['rss']['feeds']['feedname']
    assert {'name': 'feedname', 'url': FEED_VALID, 'channel': '#channel'} == feed


def test_feed_check_feed_valid(bot, feedreader_feed_valid):
    checkresults = rss._feed_check(bot, feedreader_feed_valid, '#newchannel', 'newname')
    assert not checkresults


def test_feed_check_feedname_must_be_unique(bot, feedreader_feed_valid):
    checkresults = rss._feed_check(bot, feedreader_feed_valid, '#newchannel', 'feed1')
    expected = [rss.MESSAGES['feed_name_already_in_use'].format('feed1')]
    assert expected == checkresults


def test_feed_check_channel_must_start_with_hash(bot, feedreader_feed_valid):
    checkresults = rss._feed_check(bot, feedreader_feed_valid, 'nohashsign', 'newname')
    expected = [rss.MESSAGES['channel_must_start_with_a_hash_sign'].format('nohashsign')]
    assert expected == checkresults


def test_feed_check_feed_invalid(bot, feedreader_feed_invalid):
    checkresults = rss._feed_check(bot, feedreader_feed_invalid, '#channel', 'newname')
    expected = [rss.MESSAGES['unable_to_read_feed'].format('nohashsign')]
    assert expected == checkresults


def test_feed_check_feed_item_must_have_title_or_description(bot, feedreader_feed_item_neither_title_nor_description):
    checkresults = rss._feed_check(bot, feedreader_feed_item_neither_title_nor_description, '#newchannel', 'newname')
    expected = [rss.MESSAGES['feed_items_have_neither_title_nor_description']]
    assert expected == checkresults


def test_feed_delete_delete_db_table(bot):
    rss._feed_add(bot, '#channel', 'feedname', FEED_VALID)
    rss._feed_delete(bot, 'feedname')
    result = rss._db_check_if_table_exists(bot, 'feedname')
    assert [] == result


def test_feed_delete_delete_ring_buffer(bot):
    rss._feed_add(bot, '#channel', 'feedname', FEED_VALID)
    rss._feed_delete(bot, 'feedname')
    assert 'feedname' not in bot.memory['rss']['hashes']


def test_feed_delete_delete_feed(bot):
    rss._feed_add(bot, 'channel', 'feed', FEED_VALID)
    rss._feed_delete(bot, 'feed')
    assert 'feed' not in bot.memory['rss']['feeds']


def test_feed_exists_passes(bot):
    assert rss._feed_exists(bot, 'feed1') == True


def test_feed_exists_fails(bot):
    assert rss._feed_exists(bot, 'nofeed') == False


def test_feed_list_format(bot):
    rss._feed_add(bot, 'channel', 'feed', FEED_VALID, 'ft+ftldsapg')
    rss._feed_list(bot, 'feed')
    expected = 'channel feed ' + FEED_VALID + ' ft+ftldsapg\n'
    assert expected == bot.output


def test_feed_update_print_messages(bot, feedreader_feed_valid):
    rss._feed_update(bot, feedreader_feed_valid, 'feed1', True)
    expected = bold('[feed1]') + ' Title 1 ' + bold('→') + " http://www.site1.com/article1\n" + bold('[feed1]') + ' Title 2 ' + bold('→') + " http://www.site1.com/article2\n" + bold('[feed1]') + ' Title 3 ' + bold('→') + " http://www.site1.com/article3\n"
    assert expected == bot.output


def test_feed_update_store_hashes(bot, feedreader_feed_valid):
    rss._feed_update(bot, feedreader_feed_valid, 'feed1', True)
    expected = ['4a8c89da09811991825b2263a4f9a7e0', '1f1c02250ee0f37ee99542a58fe266de', '53d66294d8b4313baf22d3ef62cb4cec']
    hashes = bot.memory['rss']['hashes']['feed1'].get()
    assert expected == hashes


def test_feed_update_no_update(bot, feedreader_feed_valid):
    rss._feed_update(bot, feedreader_feed_valid, 'feed1', True)
    bot.output = ''
    rss._feed_update(bot, feedreader_feed_valid, 'feed1', False)
    assert '' == bot.output


def test_hashes_read(bot, feedreader_feed_valid):
    rss._feed_update(bot, feedreader_feed_valid, 'feed1', True)
    expected = ['4a8c89da09811991825b2263a4f9a7e0', '1f1c02250ee0f37ee99542a58fe266de', '53d66294d8b4313baf22d3ef62cb4cec']
    bot.memory['rss']['hashes']['feed1'] = rss.RingBuffer(100)
    rss._hashes_read(bot, 'feed1')
    hashes = bot.memory['rss']['hashes']['feed1'].get()
    assert expected == hashes


def test_help_config_formats(bot):
    rss._help_config(bot, ['help', 'config', 'formats'])
    expected = rss.CONFIG['formats']['synopsis'].format(bot.config.core.prefix) + '\n'
    for message in rss.CONFIG['formats']['helptext']:
        expected += message + '\n'
    expected += rss.MESSAGES['examples'] + '\n'
    for message in rss.CONFIG['formats']['examples']:
        expected += message.format(bot.config.core.prefix) + '\n'
    assert expected == bot.output


def test_help_text_del(bot):
    rss._help_text(bot, rss.COMMANDS, 'del')
    expected = rss.COMMANDS['del']['synopsis'].format(bot.config.core.prefix) + '\n'
    for message in rss.COMMANDS['del']['helptext']:
        expected += message + '\n'
    expected += rss.MESSAGES['examples'] + '\n'
    for message in rss.COMMANDS['del']['examples']:
        expected += message.format(bot.config.core.prefix) + '\n'
    assert expected == bot.output


def test_feedformater_get_format_custom(bot, feedreader_feed_valid):
    ff = rss.FeedFormater(bot, feedreader_feed_valid, 'ta+ta')
    assert 'ta+ta' == ff.get_format()


def test_feedformater_get_format_default(bot, feedreader_feed_valid):
    ff = rss.FeedFormater(bot, feedreader_feed_valid)
    assert ff.get_default() == ff.get_format()


def test_feedformater_get_fields_feed_valid(bot, feedreader_feed_valid):
    ff = rss.FeedFormater(bot, feedreader_feed_valid)
    fields = ff.get_fields()
    assert 'fadglpsty' == fields


def test_feedformater_get_fields_feed_item_neither_title_nor_description(bot, feedreader_feed_item_neither_title_nor_description):
    ff = rss.FeedFormater(bot, feedreader_feed_item_neither_title_nor_description)
    fields = ff.get_fields()
    assert 'd' not in fields and 't' not in fields


def test_feedformater_check_format_default(bot, feedreader_feed_valid):
    ff = rss.FeedFormater(bot, feedreader_feed_valid)
    assert ff.get_default() == ff.get_format()


def test_feedformater_check_format_hashed_empty(bot, feedreader_feed_valid):
    format = '+t'
    ff = rss.FeedFormater(bot, feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_feedformater_check_format_output_empty(bot, feedreader_feed_valid):
    format = 't'
    ff = rss.FeedFormater(bot, feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_feedformater_check_format_hashed_only_feedname(bot, feedreader_feed_valid):
    format = 'f+t'
    ff = rss.FeedFormater(bot, feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_feedformater_check_format_output_only_feedname(bot, feedreader_feed_valid):
    format = 't+f'
    ff = rss.FeedFormater(bot, feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_feedformater_check_format_duplicate_separator(bot, feedreader_feed_valid):
    format = 't+t+t'
    ff = rss.FeedFormater(bot, feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_feedformater_check_format_duplicate_field_hashed(bot,feedreader_feed_valid):
    format = 'll+t'
    ff = rss.FeedFormater(bot, feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_feedformater_check_format_duplicate_field_output(bot, feedreader_feed_valid):
    format = 'l+tll'
    ff = rss.FeedFormater(bot, feedreader_feed_valid, format)
    assert format != ff.get_format()


def test_feedformater_check_format_tinyurl(bot, feedreader_feed_valid):
    format = 'fy+ty'
    ff = rss.FeedFormater(bot, feedreader_feed_valid, format)
    assert format == ff.get_format()


def test_feedformater_check_tinyurl_output(bot, feedreader_feed_valid):
    format = 'fy+ty'
    ff = rss.FeedFormater(bot, feedreader_feed_valid, format)
    item = feedreader_feed_valid.get_feed().entries[0]
    post = ff.get_post('feed1', item)
    expected = 'Title 3 \x02→\x02 https://tinyurl.com/govvpmm'
    assert expected == post


def test_feedformater_check_template_valid(bot):
    template = '{}'
    result = rss.FeedFormater(bot, rss.FeedReader('')).is_template_valid(template)
    assert True == result


def test_feedformater_check_template_invalid_no_curly_braces(bot):
    template = ''
    result = rss.FeedFormater(bot, rss.FeedReader('')).is_template_valid(template)
    assert False == result


def test_feedformater_check_template_invalid_duplicate_curly_braces(bot):
    template = '{}{}'
    result = rss.FeedFormater(bot, rss.FeedReader('')).is_template_valid(template)
    assert False == result


def test_ringbuffer_append():
    rb = rss.RingBuffer(3)
    assert rb.get() == []
    rb.append('1')
    assert ['1'] == rb.get()


def test_ringbuffer_overflow():
    rb = rss.RingBuffer(3)
    rb.append('hash1')
    rb.append('hash2')
    rb.append('hash3')
    assert ['hash1', 'hash2', 'hash3'] == rb.get()
    rb.append('hash4')
    assert ['hash2', 'hash3', 'hash4'] == rb.get()
