# Extract articles in markdown format

## stack 
Python 3.14

## usage
Input data options:  
--start dd.mm.yyyy  
--end dd.mm.yyyy  
--dir /path/to/markdown/storage/dir

## action
Do steps 1 and 2 for each date in range(start, end) including start and end dates.
Then step 3 - with created list of href articles, do iteration over the list and process each item and store md file for each item in dir.

### step 1 - Download page for link
https://www.theguardian.com/world/russia/[yyyy]/[MONTH-EN-THREE-SYMBOLS]/[dd]/all

example:
https://www.theguardian.com/world/russia/2026/oct/10/all

### step 2 - Parse dowloaded page
Find all references (a tag) with class=js-headline-text

Example:
```html
<a href="https://www.theguardian.com/world/2026/oct/10/ukraine-war-briefing-trumps-russian-diesel-deal-derided-as-weak-and-a-betrayal-of-ukraine-and-us-national-security" class="u-faux-block-link__overlay js-headline-text" data-link-name="article" tabindex="-1" aria-hidden="true">Ukraine war briefing: Kyiv blasts peace talks as just ‘smokescreen’ for Trump‘s Russian diesel deal</a>
```

Add value of href to List. If href already in list log warning.

### step 3 - Download each article link and extract md
Do iteration over href links.   
Downloload page by href link.
Transform an article inside tag <article> to markdown file.
Store md file in dir/dd.mm.yyyy/<article-mnemocode-from-href>.md
article-mnemocode-from-href - part of href link after slash that comes after date and to the end.


