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

### rss config &mdash; get and set configuration values

**Synopsis:** *.rss config \<key\> [\<value\>]*

Get a *\<key\>* from the configuration file or set a *\<value\>* of a *\<key\>* and the consequences will be applied immediately. Use *.rss help config* to see which keys are available. Use *.rss help config \<key\>* to get a detailed explanation of *\<key\>*. 

### rss del &mdash; delete a feed

**Synopsis:** *.rss del \<name\>*

Delete the feed called \<name\>.

### rss fields &mdash; get feed item fields

**Synopsis:** *.rss fields \<name\>*

Get the item fields of the feed *\<name\>*. 

### rss format &mdash; set the format of a feed

**Synopsis:** *.rss format \<name\> \<format\>*

Set the format of the feed *\<name\>* to *\<format\>*. 

### rss get &mdash; read a feed and post new items

**Synopsis:** *.rss get \<name\>*

Post all items of the feed to the channel of the feed. Mainly useful for debugging.

### rss help &mdash; get help online

**Synopsis:** *.rss help [\<command\>]*

Get a list of available commands or get a detailed explanation of a command. Have a look at *.rss help config*. 

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

The following options can be set in the configuration file or via *.rss config \<key\> \<value\>*. The configuration file will be read when the bot is (re)started or when the owner or an admin issues the command *.reload rss* in a query with the bot. Be aware that the bot mustn't be running when editing the configuration file. Otherwise, your edits may be overwritten!

### feeds &mdash; *which* feeds will be posted *where*

**Synopsis:** *.rss config feeds \<channel1\>|\<name1\>|\<url1\>|[\<format1\>],\<channel2\>|\<name2\>|\<url2\>|[\<format2\>]...*

Comma separated list of feed definitions with channel, feedname, url and optionally format separated by pipes.

### formats &mdash; *what* fields of the feed items will be posted

**Synopsis:** *.rss config formats \<format1\>,\<format2\>,...*

Comma separated list of default formats which will be used if the fields of the feed fit the format.

### templates &mdash; *how* the feed items will be posted

**Synopsis:** *.rss config templates \<field1\>|\<template1\>,\<field2\>|\<template2\>...*

Comma separated list of template strings which will override the default template strings. Curly braces will be replaced by the actual string. In the template strings the field and template are separated by a pipe.

## Formats

A *format* string defines which feed item fields be be hashed, i.e. when two feed items will be considered equal, and which field item fields will be output by the bot. Both definitions are separated by a '+'. Each valid rss feed must have at least a title or a description field, all other item fields are optional. These fields can be configured for sopel-rss:

|field|caption    |
|-----|-----------|
|f    |feedname   |
|a    |author     |
|d    |description|
|g    |guid       |
|l    |link       |
|p    |published  |
|s    |summary    |
|t    |title      |
|y    |tinyurl    |

The feedname is a custom name specified as a parameter to *.rss add* an not a feed item field. guid is a unique identifiert and published is the date and time of publication. tinyurl will work like the field link but it will shorten the url through [tinyurl](https://www.tinyurl.com/) first.

Example: *fl+tl*

The feedname and the link of the rss feed item will be used to hash the feed item. If an item of a different feed has the same link it will be posted again by the bot. The bot will post the feed item title followed by the feed item link.

Example: *flst+tal*

The feedname, link, summary and title will be used to hash the feed item. If any of these fields change in the feed the feed item will be posted again. The bot will post the title, author and link of the feed item but not the feedname.

## Templates

Template strings define how the different fields of a feed item will be posted to the irc channel. You may override some or all of the default template strings. Curly braces {} will be replaced by the field value. These are the default templates:


|field|template  |
|-----|----------|
|f    |%16[{}]%20|
|a    |{}        |
|d    |{}        |
|g    |{}        |
|l    |%16→%20 {}|
|p    |{}        |
|s    |{}        |
|t    |{}        |
|y    |%16→%20 {}|

You can use nearly any character you like but the percent sign % has a special meaning: it is the escape sign. If you want the bot to print a percent sign then you have to specify it twice: if the title of an item is "itemtitle" then *t|%%{}* will output "%itemtitle". The same is true for a comma after an escape sequence: if the title of an item is "itemtitle" then *t|%17%,{}%20* will output ",itemtitle" in italics.

To print colors you have to use the percent sign the color code of a foreground color. Optionally you can add a dollar sign the color code of a background color. Here is a list of all valid color and other formatting codes:
 
|code|name                            |
|----|--------------------------------|
|00  |white                           |
|01  |black                           |
|02  |blue (navy)                     |
|03  |green                           |
|04  |red                             |
|05  |brown (maroon)                  |
|06  |purple                          |
|07  |orange (olive)                  |
|08  |yellow                          |
|09  |light green (lime)              |
|10  |teal (a green/blue cyan)        |
|11  |light cyan (cyan / aqua)        |
|12  |light blue (royal)              |
|13  |pink (light purple / fuchsia)   |
|14  |grey                            |
|15  |light grey (silver)             |
|16  |bold                            |
|17  |italic                          |
|18  |underline                       |
|19  |switch colors / "reverse video" |
|20  |reset formatting                |

The command *.rss config templates* will show you the current template strings and a matching example output. This is the output of *.rss config templates* for the default template string (i.e. the value of *templates* in the config file is empty):

a|<{}>,d|{},f|%16[{}]%16,g|{},l|%16→%16 {},p|({}),s|{},t|{},y|%16→%16 {}

<Author> Description **[Feedname]** http://www.example.com/GUID **→** https://github.com/RebelCodeBase/sopel-rss (2016-09-03 10:00) Description Title **→** https://tinyurl.com/govvpmm

Example: *.rss config templates t|%18%17{}%17%18*

Underline the title and print it in italics.

Example: *.rss config templates p|%09({})%20*

Print the time in parentheses and in bright green. Stop the formatting afterwards so that the following fields are not affected by the color change.

Example: *.rss config templates f|%13$15%16[{}]%16*

Print the feedname in pink on silver in bold. The %16 will stop the bold formatting but as there is no %20 to reset formatting, everything after the field f (depending on the format) will be printed in pink on silver as well.

## Unit Tests

This module is extensively tested through [py.test](http://doc.pytest.org):

`python3 -m pytest -v sopel/modules/rss.py test/test_rss.py`

## License

This project is licensed under the GNU General Public License.

## Notes

I came across [f4bio/sopel-rss](https://github.com/f4bio/sopel-rss) when I was looking for an rss2irc app. First, I've forked his repo but then the coding took a very different turn so I decided to create a new repository. f4bio, thanks a lot for your inspiration!
