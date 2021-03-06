from django.shortcuts import get_object_or_404, render
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect

from demoscene.shortcuts import get_page, simple_ajax_form, simple_ajax_confirmation
from demoscene.models import Releaser, Nick, Membership, Edit
from demoscene.forms.releaser import ScenerEditLocationForm, ScenerEditRealNameForm, CreateScenerForm, ScenerMembershipForm

from django.contrib.auth.decorators import login_required
import datetime
from read_only_mode import writeable_site_required


def index(request):

	nick_page = get_page(
		Nick.objects.filter(releaser__is_group=False).extra(
			select={'lower_name': 'lower(demoscene_nick.name)'}
		).order_by('lower_name'),
		request.GET.get('page', '1'))

	return render(request, 'sceners/index.html', {
		'nick_page': nick_page,
	})


def show(request, scener_id, edit_mode=False):
	scener = get_object_or_404(Releaser, id=scener_id)
	if scener.is_group:
		return HttpResponseRedirect(scener.get_absolute_url())

	user_has_real_name_access = request.user.has_perm('demoscene.view_releaser_real_names')

	external_links = scener.external_links.select_related('releaser').defer('releaser__notes')
	if not request.user.is_staff:
		external_links = external_links.exclude(link_class='SlengpungUser')
	if not user_has_real_name_access and not scener.can_reveal_full_real_name():
		external_links = external_links.exclude(link_class__in=['MobygamesDeveloper', 'HallOfLightArtist'])

	external_links = sorted(external_links, key=lambda obj: obj.sort_key)

	return render(request, 'sceners/show.html', {
		'scener': scener,
		'external_links': external_links,
		'editing_groups': (request.GET.get('editing') == 'groups'),
		'productions': scener.productions().select_related('default_screenshot').prefetch_related('author_nicks__releaser', 'author_affiliation_nicks__releaser', 'platforms', 'types').defer('notes', 'author_nicks__releaser__notes', 'author_affiliation_nicks__releaser__notes').order_by('-release_date_date', '-title'),
		'credits': scener.credits().select_related('nick', 'production__default_screenshot').prefetch_related('production__author_nicks__releaser', 'production__author_affiliation_nicks__releaser', 'production__platforms', 'production__types').defer('production__notes', 'production__author_nicks__releaser__notes', 'production__author_affiliation_nicks__releaser__notes').order_by('-production__release_date_date', 'production__title', 'production__id', 'nick__name', 'nick__id'),
		'memberships': scener.group_memberships.select_related('group').defer('group__notes').order_by('-is_current', 'group__name'),
		'user_has_real_name_access': user_has_real_name_access
	})


def history(request, scener_id):
	scener = get_object_or_404(Releaser, is_group=False, id=scener_id)
	return render(request, 'sceners/history.html', {
		'scener': scener,
		'edits': Edit.for_model(scener, request.user.is_staff),
	})


@writeable_site_required
@login_required
def edit_location(request, scener_id):
	scener = get_object_or_404(Releaser, is_group=False, id=scener_id)

	def success(form):
		form.log_edit(request.user)

	return simple_ajax_form(request, 'scener_edit_location', scener, ScenerEditLocationForm,
		title='Editing location for %s:' % scener.name,
		update_datestamp=True, on_success=success)


@writeable_site_required
@login_required
def edit_real_name(request, scener_id):
	scener = get_object_or_404(Releaser, is_group=False, id=scener_id)
	if not request.user.has_perm('demoscene.view_releaser_real_names'):
		return HttpResponseRedirect(scener.get_absolute_edit_url())

	def success(form):
		form.log_edit(request.user)

	return simple_ajax_form(request, 'scener_edit_real_name', scener, ScenerEditRealNameForm,
		title="Editing %s's real name:" % scener.name,
		update_datestamp=True, on_success=success, ajax_submit=request.GET.get('ajax_submit'))


@writeable_site_required
@login_required
def create(request):
	if request.method == 'POST':
		scener = Releaser(is_group=False, updated_at=datetime.datetime.now())
		form = CreateScenerForm(request.POST, instance=scener)
		if form.is_valid():
			form.save()
			form.log_creation(request.user)
			return HttpResponseRedirect(scener.get_absolute_edit_url())
	else:
		form = CreateScenerForm()

	return render(request, 'shared/simple_form.html', {
		'form': form,
		'html_title': "New scener",
		'title': "New scener",
		'action_url': reverse('new_scener'),
	})


@writeable_site_required
@login_required
def add_group(request, scener_id):
	scener = get_object_or_404(Releaser, is_group=False, id=scener_id)
	if request.method == 'POST':
		form = ScenerMembershipForm(request.POST)
		if form.is_valid():
			group = form.cleaned_data['group_nick'].commit().releaser
			if not scener.group_memberships.filter(group=group).count():
				membership = Membership(
					member=scener,
					group=form.cleaned_data['group_nick'].commit().releaser,
					is_current=form.cleaned_data['is_current'])
				membership.save()
				scener.updated_at = datetime.datetime.now()
				scener.save()
				description = u"Added %s as a member of %s" % (scener.name, group.name)
				Edit.objects.create(action_type='add_membership', focus=scener, focus2=group,
					description=description, user=request.user)
			return HttpResponseRedirect(scener.get_absolute_edit_url() + "?editing=groups")
	else:
		form = ScenerMembershipForm()

	return render(request, 'sceners/add_group.html', {
		'scener': scener,
		'form': form,
	})


@writeable_site_required
@login_required
def remove_group(request, scener_id, group_id):
	scener = get_object_or_404(Releaser, is_group=False, id=scener_id)
	group = get_object_or_404(Releaser, is_group=True, id=group_id)
	if request.method == 'POST':
		deletion_type = request.POST.get('deletion_type')
		if deletion_type == 'ex_member':
			# set membership to is_current=False - do not delete
			scener.group_memberships.filter(group=group).update(is_current=False)
			scener.updated_at = datetime.datetime.now()
			scener.save()
			Edit.objects.create(action_type='edit_membership', focus=scener, focus2=group,
				description=u"Updated %s's membership of %s: set as ex-member" % (scener.name, group.name),
				user=request.user)
			return HttpResponseRedirect(scener.get_absolute_edit_url() + "?editing=groups")
		elif deletion_type == 'full':
			scener.group_memberships.filter(group=group).delete()
			scener.updated_at = datetime.datetime.now()
			scener.save()
			description = u"Removed %s as a member of %s" % (scener.name, group.name)
			Edit.objects.create(action_type='remove_membership', focus=scener, focus2=group,
				description=description, user=request.user)
			return HttpResponseRedirect(scener.get_absolute_edit_url() + "?editing=groups")
		else:
			show_error_message = True

	else:
		show_error_message = False

	return render(request, 'sceners/remove_group.html', {
		'scener': scener,
		'group': group,
		'show_error_message': show_error_message,
	})


@writeable_site_required
@login_required
def edit_membership(request, scener_id, membership_id):
	scener = get_object_or_404(Releaser, is_group=False, id=scener_id)
	membership = get_object_or_404(Membership, member=scener, id=membership_id)
	if request.method == 'POST':
		form = ScenerMembershipForm(request.POST)
		if form.is_valid():
			group = form.cleaned_data['group_nick'].commit().releaser
			if not scener.group_memberships.exclude(id=membership_id).filter(group=group).count():
				membership.group = group
				membership.is_current = form.cleaned_data['is_current']
				membership.save()
				scener.updated_at = datetime.datetime.now()
				scener.save()
				form.log_edit(request.user, scener, group)
			return HttpResponseRedirect(scener.get_absolute_edit_url() + "?editing=groups")
	else:
		form = ScenerMembershipForm(initial={
			'group_nick': membership.group.primary_nick,
			'is_current': membership.is_current,
		})
	return render(request, 'sceners/edit_membership.html', {
		'scener': scener,
		'membership': membership,
		'form': form,
	})


@writeable_site_required
@login_required
def convert_to_group(request, scener_id):
	scener = get_object_or_404(Releaser, is_group=False, id=scener_id)
	if not request.user.is_staff or not scener.can_be_converted_to_group():
		return HttpResponseRedirect(scener.get_absolute_edit_url())
	if request.method == 'POST':
		if request.POST.get('yes'):
			scener.is_group = True
			scener.updated_at = datetime.datetime.now()
			scener.save()
			Edit.objects.create(action_type='convert_to_group', focus=scener,
				description=(u"Converted %s from a scener to a group" % scener), user=request.user)
		return HttpResponseRedirect(scener.get_absolute_edit_url())
	else:
		return simple_ajax_confirmation(request,
			reverse('scener_convert_to_group', args=[scener_id]),
			"Are you sure you want to convert %s into a group?" % (scener.name),
			html_title="Converting %s to a group" % (scener.name))
