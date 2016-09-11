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

#### Synopsis: *.rss add \<channel\> \<name\> \<url\> [\<options\>]*

Add the feed *\<url\>* to *\<channel\>* and call it *\<name\>*. Options may be specified, see Formats and Templates. The feed will be read approximately every minute and new items will be automatically posted to *\<channel\>*.

### rss config &mdash; get or set configuration values

#### Synopsis: *.rss config \<key\> [\<value\>]*

Get a *\<key\>* from the configuration file or set a *\<value\>* of a *\<key\>* and the consequences will be applied immediately. Use *.rss help config* to see which keys are available. Use *.rss help config \<key\>* to get a detailed explanation of *\<key\>*. 

### rss del &mdash; delete a feed

#### Synopsis: *.rss del \<name\>*

Delete the feed called \<name\>.

### rss fields &mdash; get feed item fields

#### Synopsis: *.rss fields \<name\>*

Get the item fields of the feed *\<name\>*. 

### rss formats &mdash; get or set the format of a feed

#### Synopsis: *.rss formats \<name\> [f=\<format\>]*

Get the format of the feed *\<name\>*. Or set the format of the feed *\<name\>* to *\<format\>*. 

### rss get &mdash; read a feed and post new items

#### Synopsis: *.rss get \<name\>*

Post all items of the feed to the channel of the feed. Mainly useful for debugging.

### rss help &mdash; get help online

#### Synopsis: *.rss help [\<command\>]*

Get a list of available commands or get a detailed explanation of a command. Have a look at *.rss help config*. 

### rss list &mdash; list feeds

#### Synopsis: *.rss list [\<feed\>|\<channel\>]*

List properties of \<feed\> or list all feeds in \<channel\>. 

### rss join &mdash; join all feeds' channels

#### Synopsis: *.rss join*

Every feed must have a channel associated to it and *.rss join* joins these channels. This command is only needed in case of problems as channels are automatically joind after adding a feed or restarting the bot.
 
### rss templates &mdash; get or set the templates of a feed

#### Synopsis: *.rss templates \<name\> [t=\<field1\>|\<template1\>;t=\<field1\>|\<template1\>;...]*

Get the templates of the feed *\<name\>*. Or set templates of the feed *\<name\>*. 

### rss update &mdash; post new feed items

#### Synopsis: *.rss update*

Calls the internal function which updates the feed every minute. This command is only needed if you want new feed items to be posted immediately.

## Options

The following options can be set in the configuration file or via *.rss config \<key\> \<value\>*. The configuration file will be read when the bot is (re)started or when the owner or an admin issues the command *.reload rss* in a query with the bot. Be aware that the bot mustn't be running when editing the configuration file. Otherwise, your edits may be overwritten!

### feeds &mdash; *which* feeds will be posted *where*

#### Synopsis: *.rss config feeds \<channel1\>;\<name1\>;\<url1\>[\;<options1\>],\<channel2\>;\<name2\>;\<url2\>[\;<options2\>]...*

Comma separated list of feed definitions with channel, feedname, url and optionally format separated by semicolons.

### formats &mdash; *what* fields of the feed items will be posted

#### Synopsis: *.rss config formats f=\<format1\>;f=\<format2\>,...*

Semicolon separated list of default formats which will be used if the fields of the feed fit the format.

### templates &mdash; *how* the feed items will be posted

#### Synopsis: *.rss config templates t=\<field1\>|\<template1\>;t=\<field2\>|\<template2\>...*

Semicolon separated list of template strings which will override the default template strings. Curly brackets will be replaced by the actual string. In the template strings the field and template are separated by a pipe.

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

The field f references the feedname and is not a feed item field, guid is a unique identifiert and published is the date and time of publication. tinyurl will work like the field link but it will shorten the url through [tinyurl](https://www.tinyurl.com/) first.

#### Example: *.rss config formats f=fl+tl*

The feedname and the link of the rss feed item will be used to hash the feed item. If an item of a different feed has the same link it will be posted again by the bot. The bot will post the feed item title followed by the feed item link.

#### Example: *.rss config formats f=flst+tal*

The feedname, link, summary and title will be used to hash the feed item. If any of these fields change in the feed the feed item will be posted again. The bot will post the title, author and link of the feed item but not the feedname.

## Templates

Template strings define how the different fields of a feed item will be posted to the irc channel. You may override some or all of the default template strings. Curly brackets {} will be replaced by the field value. These are the default templates:


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

You can use nearly any character you like but the percent sign % has a special meaning: it is the escape sign. If you want the bot to print a percent sign then you have to specify it twice: if the title of an item is "itemtitle" then *t=t|%%{}* will output "%itemtitle". The same is true for a comma after an escape sequence: if the title of an item is "itemtitle" then *t=t|%17%,{}%20* will output ",itemtitle" in italics.

To print colors you have to use the percent sign the color code of a foreground color. Optionally you can add a dollar sign the color code of a background color. Here is a list of all valid color and other formatting codes:

<table>
  <tr align=left>
    <th>code</th>
    <th>name</th>
  </tr>
  <tr style="color:#000000;background:#FFFFFF">
    <td>00</td>
    <td>white</td>
  </tr>
  <tr style="color:#FFFFFF;background:#000000">
    <td>01</td>
    <td>black</td>
  </tr>
  <tr style="color:#FFFFFF;background:#00007F">
    <td>02</td>
    <td>blue</td>
  </tr>
  <tr style="color:#FFFFFF;background:#009300">
    <td>03</td>
    <td>green</td>
  </tr>
  <tr style="color:#FFFFFF;background:#FF0000">
    <td>04</td>
    <td>red</td>
  </tr>
  <tr style="color:#FFFFFF;background:#7F0000">
    <td>05</td>
    <td>brown (maroon)</td>
  </tr>
  <tr style="color:#FFFFFF;background:#9C009C">
    <td>06</td>
    <td>purple</td>
  </tr>
  <tr style="color:#FFFFFF;background:#FC7F00">
    <td>07</td>
    <td>orange (olive)</td>
  </tr>
  <tr style="color:#000000;background:#FFFF00">
    <td>08</td>
    <td>yellow</td>
  </tr>
  <tr style="color:#000000;background:#00FC00">
    <td>09</td>
    <td>light green (lime)</td>
  </tr>
  <tr style="color:#FFFFFF;background:#009393">
    <td>10</td>
    <td>teal (a green/blue cyan)</td>
  </tr>
  <tr style="color:#000000;background:#00FFFF">
    <td>11</td>
    <td>light cyan (cyan / aqua)</td>
  </tr>
  <tr style="color:#FFFFFF;background:#0000FC">
    <td>12</td>
    <td>light blue (royal)</td>
  </tr>
  <tr style="color:#FFFFFF;background:#FF00FF">
    <td>13</td>
    <td>pink (light purple / fuchsia)</td>
  </tr>
  <tr style="color:#FFFFFF;background:#7F7F7F">
    <td>14</td>
    <td>grey</td>
  </tr>
  <tr style="color:#000000;background:#D2D2D2">
    <td>15</td>
    <td>light grey (silver) </td>
  </tr>
  <tr>
    <td>16</td>
    <td><b>bold</b></td>
  </tr>
  <tr>
    <td>17</td>
    <td><i>italic</i></td>
  </tr>
  <tr>
    <td>18</td>
    <td><u>underline</u></td>
  </tr>
  <tr>
    <td>19</td>
    <td><span style="color:#9C009C;background:#FFFF00">switch colors / </span><span style="color:#FFFF00;background:#9C009C"> "reverse video"</span></td>
  </tr>
  <tr>
    <td>20</td>
    <td>reset formatting </td>
  </tr>
</table>

The command *.rss config templates* will show you the current template strings and a matching example output. This is the output of *.rss config templates* for the default template string (i.e. the value of *templates* in the config file is empty):

t=a|<{}>;t=d|{};t=f|%16[{}]%16;t=g|{};t=l|%16→%16 {};t=p|({});t=s|{};t=t|{};t=y|%16→%16 {}

<Author> Description **[Feedname]** http://www.example.com/GUID **→** https://github.com/RebelCodeBase/sopel-rss (2016-09-03 10:00) Description Title **→** https://tinyurl.com/govvpmm

#### Example: *.rss config templates t=t|%18%17{}%17%18*

Underline the title and print it in italics.

#### Example: *.rss config templates t=p|%09({})%20*

Print the time in parentheses and in bright green. Stop the formatting afterwards so that the following fields are not affected by the color change.

#### Example: *.rss config templates "t=l| → {}"*

Include spaces in a template by using quotes.

#### Example: *.rss config templates t=f|%13$15%16[{}]%16*

Print the feedname in pink on silver in bold. The %16 will stop the bold formatting but as there is no %20 to reset formatting, everything after the field f (depending on the format) will be printed in pink on silver as well.

## Unit Tests

This module is extensively tested through [py.test](http://doc.pytest.org):

`python3 -m pytest -v sopel/modules/rss.py test/test_rss.py`

## License

This project is licensed under the GNU General Public License.

## Notes

I came across [f4bio/sopel-rss](https://github.com/f4bio/sopel-rss) when I was looking for an rss2irc app. First, I've forked his repo but then the coding took a very different turn so I decided to create a new repository. f4bio, thanks a lot for your inspiration!
