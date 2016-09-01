# sopel-rss

[sopel-rss](https://github.com/RebelCodeBase/sopel-rss) is an [RSS](https://en.wikipedia.org/wiki/RSS) module for the [IRC](https://en.wikipedia.org/wiki/Internet_Relay_Chat) bot framework [sopel](https://github.com/sopel-irc/sopel). 

## Deployment

The [Ansible](https://en.wikipedia.org/wiki/Ansible_(software)) role [ansible-role-sopel-runit-debian](https://github.com/RebelCodeBase/ansible-role-sopel-runit-debian) can be used to deploy the bot from [Github](https://en.wikipedia.org/wiki/GitHub) to [Debian](https://en.wikipedia.org/wiki/Debian) using [runit](https://en.wikipedia.org/wiki/Runit).

## Installation

Put *rss.py* in your *~/.sopel/modules* directory.

## Usage

The rss module posts items of rss feeds to irc channels. It hashes the feed items and stores the hashes in a ring buffer in memory and in a sqlite database on disk. It uses one ring buffer and one database table per feed in order to avoid reposting old feed items.

## Commands

All commands require owner or admin privileges.

### rss add &mdash; add a feed

**Synopsis:** *.rss add \<channel\> \<name\> \<url\> [\<format\>]*

Add the feed *\<url\>* to *\<channel\>* and call it *\<name\>*. Optionally, a format can be specified, see section Format. The feed will be read approximately every minute and new items will be automatically posted to *\<channel\>*.

### rss del &mdash; delete a feed

**Synopsis:** *.rss del \<name\>*

Delete the feed called \<name\>.

### rss get &mdash; read a feed and post new items

**Synopsis:** *.rss get \<name\>*

Post all items of the feed to the channel of the feed. Mainly useful for debugging.

### rss list &mdash; list feeds

**Synopsis:** *.rss list [\<feed\>|\<channel\>]*

List properties of \<feed\> or list all feeds in \<channel\>. 

### rss join &mdash; join all feeds' channels

**Synopsis:** *.rss join*

Every feed must have a channel associated to it and *.rss join* joins these channels. This command is only needed in case of problems as channels are automatically joind after adding a feed or restarting the bot.
 
### rss update &mdash; post new feed items

**Synopsis:** *.rss update*

Calls the internal function which updates the feed every minute. This command is only needed if you want new feed items to be posted immediately.

## Options

The following options can be set in the configuration file. Be aware that the bot mustn't be running when editing the configuration file. Otherwise, your edits may be overwritten!

**Synopsis:** *feeds=\<channel1\> \<name1\> \<url1\> [\<format1\>][,\<channel2\> \<name2\> \<url2\> [\<format2\>]]...*

*Default:* empty

This is the main data of the bot which will be read when the bot is started or when the owner or an admin issues the command *.reload rss* in a query with the bot.

## Formats

A *format* string defines which feed item fields be be hashed, i.e. when two feed items will be considered equal, and which field item fields will be output by the bot. Both definitions are separated by a '+'. Each valid rss feed must have at least a title or a description field, all other item fields are optional. These fields can be configured for sopel-rss:

<table>
    <tr>
        <td>f</td>
        <td>feedname</td>
    </tr>
    <tr>
        <td>a</td>
         <td>author</td>
    </tr>
    <tr>
        <td>d</td>
        <td>description</td>
    </tr>
    <tr>
        <td>g</td>
         <td>guid</td>
    </tr>
    <tr>
        <td>l</td>
         <td>link</td>
    </tr>
    <tr>
        <td>p</td>
         <td>published</td>
    </tr>
    <tr>
        <td>s</td>
         <td>summary</td>
    </tr>
    <tr>
        <td>t</td>
         <td>title</td>
    </tr>
    <tr>
        <td>u</td>
         <td>titnyurl</td>
    </tr>
</table>

The feedname is a custom name specified as a parameter to *.rssadd* an not a feed item field. guid is a unique identifiert and published is the date and time of publication.

Example: *fl+tl*

The feedname and the link of the rss feed item will be used to hash the feed item. If an item of a different feed has the same link it will be posted again by the bot. The bot will post the feed item title followed by the feed item link.

Example: *flst+tal*

The feedname, link, summary and title will be used to hash the feed item. If any of these fields change in the feed the feed item will be posted again. The bot will post the title, author and link of the feed item but not the feedname.

## Unit Tests

This module is extensively tested through [py.test](http://doc.pytest.org):

`python3 -m pytest -v sopel/modules/rss.py test/test_rss.py`

## License

This project is licensed under the GNU General Public License.

## Notes

I came across [f4bio/sopel-rss](https://github.com/f4bio/sopel-rss) when I was looking for an rss2irc app. First, I've forked his repo but then the coding took a very different turn so I decided to create a new repository. f4bio, thanks a lot for your inspiration!
