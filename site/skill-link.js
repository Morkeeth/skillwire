/* Old links such as /#4ce3ea8ad15789a4 open that skill in the catalog. */
(function () {
  'use strict';
  if (/^#[0-9a-f]{16}$/.test(location.hash)) location.replace('/search' + location.hash);
}());
