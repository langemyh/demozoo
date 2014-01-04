from django import template
from django.db.models import Q

from parties.models import Party
import datetime

register = template.Library()

@register.inclusion_tag('zxdemo/tags/byline.html')
def byline(production):
	return {
		'unparsed_byline': production.unparsed_byline,
		'authors': production.author_nicks.all(),
		'affiliations': production.author_affiliation_nicks.all(),
	}

@register.inclusion_tag('zxdemo/tags/forthcoming_parties.html')
def forthcoming_parties():
	# TODO: only show ones that have been marked as having Spectrum relevance?
	date_filter = Q(start_date_date__gte=datetime.date.today()) | Q(end_date_date__gte=datetime.date.today())
	return {
		'parties': Party.objects.filter(date_filter).order_by('start_date_date', 'end_date_date')
	}

@register.inclusion_tag('zxdemo/tags/date_range.html')
def date_range(start_date, end_date):
	return {
		'start_date': start_date,
		'end_date': end_date,
	}


DOWNLOAD_TYPE_ICONS = [
	('soundtrack', 'track_new.gif'),
	('VTX', 'chipmusic_new.gif'),
	('TAP', 'tape_new.gif'),
	('SCL', 'disc_new.gif'),
	('custom TAP', 'specialtape_new.gif'),
	('TZX', 'specialtape_new.gif'),
	('DivX', 'video_new.gif'),
	('Z80', 'z80.gif'),
	('AY', 'ay.gif'),
]
@register.simple_tag
def download_icon(download):
	icon_filename = 'disc_new.gif'
	if download.description:
		for prefix, filename in DOWNLOAD_TYPE_ICONS:
			if download.description.startswith(prefix):
				icon_filename = filename
				break

	return '<img src="/static/zxdemo/images/icon/%s" alt="" width="24" height="24" border="0" />' % icon_filename


@register.simple_tag
def production_type_icon(production):
	if production.supertype == 'graphics':
		return '<img src="/static/zxdemo/images/icon/gfx_new.gif" align="absmiddle" alt="[Graphics]" width="24" height="24" border="0" />'
	elif production.supertype == 'music':
		return '<img src="/static/zxdemo/images/icon/music_new.gif" align="absmiddle" alt="[Music]" width="24" height="24" border="0" />'
	else:
		return '<img src="/static/zxdemo/images/icon/demo_new.gif" align="absmiddle" alt="[Demo]" width="24" height="24" border="0" />'