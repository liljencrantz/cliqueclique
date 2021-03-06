import django.shortcuts
import django.template
import django.core.urlresolvers
import cliqueclique_node.models
import cliqueclique_document.models
import cliqueclique_subscription.models
import cliqueclique_ui_security_context.security_context
import email.mime.text
import django.http
import utils.hash
import utils.smime
import utils.djangosmime
import django.contrib.auth.decorators
import fcdjangoutils.jsonview
import secure_id
import sys
import traceback
import jogging

def obtain_secure_access(request, document_id):
    info = {}

    info['secure_document_id'] = secure_id.make_secure_id(request, document_id)
    info['document_document_id'] = document_id
    mime = cliqueclique_document.models.Document.objects.get(document_id = document_id).as_mime
    if isinstance(mime, utils.smime.MIMESigned):
        cert = mime.verify()[0]
        data = utils.smime.cert_get_data(cert)
        info['document_author_name'] = data['name']
        info['document_author_node_id'] = cliqueclique_node.models.Node.node_id_from_public_key(cert)
        info['document_author_address'] = data['address']
        mime = mime.get_payload()[0]
    info['document_subject'] = mime.get('subject', None)

    info['security_context_document_id'] = cliqueclique_ui_security_context.security_context.get_security_context(request)['owner_document_id']
    mime = cliqueclique_document.models.Document.objects.get(document_id =  info['security_context_document_id']).as_mime
    if isinstance(mime, utils.smime.MIMESigned):
        cert = mime.verify()[0]
        data = utils.smime.cert_get_data(cert)
        info['security_context_author_name'] = data['name']
        info['security_context_author_node_id'] = cliqueclique_node.models.Node.node_id_from_public_key(cert)
        info['security_context_author_address'] = data['address']
        mime = mime.get_payload()[0]
    info['security_context_subject'] = mime.get('subject', None)

    return django.shortcuts.render_to_response(
        'cliqueclique_ui_document/obtain_secure_access.html',
        info,
        context_instance=django.template.RequestContext(request))

@django.contrib.auth.decorators.login_required
def import_document(request):
    msg = request.FILES['file'].read()
    request.user.node.receive(msg)
    msg = utils.smime.message_from_anything(msg)
    container_msg = msg.get_payload()[0]
    update_msg = container_msg.get_payload()[0]
    return django.shortcuts.redirect("cliqueclique_ui.views.display_document", document_id=update_msg['document_id'])

@django.contrib.auth.decorators.login_required
def set_document_flags(request, document_id):
    sub = cliqueclique_subscription.models.DocumentSubscription.objects.get(
        node = request.user.node,
        document__document_id = document_id)
    for attr in ('bookmarked', 'read', 'local_is_subscribed'):
        if attr in request.POST:
            attrvalue = request.POST[attr]
        elif attr in request.GET:
            attrvalue = request.GET[attr]
        else:
            continue
        if attrvalue == "toggle":
            value = not getattr(sub, attr)
        elif attrvalue == "true":
            value = True
        else:
            value = False
        setattr(sub, attr, value)
    sub.save()
    return django.shortcuts.redirect("cliqueclique_ui.views.display_document", document_id=sub.document.document_id)

@django.contrib.auth.decorators.login_required
def document(request, format, document_id = None, single = False):
    try:
        print repr(request.GET.get('query', None))
        docs = list(cliqueclique_subscription.models.DocumentSubscription.get_by_query(
                q = request.GET.get('query', None),
                node_id = request.user.node.node_id,
                document_id = document_id))

        if format == 'mime':
            if len(docs) == 0:
                docs = email.mime.multipart.MIMEMultipart()
            elif len(docs) == 1:
                docs = docs[0].export()
            else:
                msg = email.mime.multipart.MIMEMultipart()
                for doc in docs:
                    msg.attach(doc.send(True))
                docs = docs[0].node.sign(msg)
            docs = docs.as_string()
            mimetype="text/plain"
        elif format == 'json':
            is_secure = False
            res = {}
            for doc in docs:
                res[doc.document.document_id] = {'document_id': doc.document.document_id,
                                                 'parents': [parent.document.document_id for parent in doc.parents.all()],
                                                 'children': [secure_id.make_secure_id(request, child.document.document_id, is_secure)
                                                              for child in doc.children.all()],
                                                 'content': doc.document.as_mime
                                                 }
            docs = django.utils.simplejson.dumps(res, default=fcdjangoutils.jsonview.jsonify_models)
            mimetype="text/plain"
    except django.core.servers.basehttp.WSGIServerException:
        raise
    except Exception, e:
        etype = sys.modules[type(e).__module__].__name__ + "." + type(e).__name__
        jogging.logging.error("%s: %s" % (str(e), etype))
        raise
        if format != 'json':
            raise
        docs = {'error': {'type': etype,
                         'description': str(e),
                         'traceback': traceback.format_exc()}}
        docs = django.utils.simplejson.dumps(docs, default=fcdjangoutils.jsonview.jsonify_models)
        mimetype="text/plain"
    return django.http.HttpResponse(docs, mimetype="text/plain")
